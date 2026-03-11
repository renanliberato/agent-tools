using System;
using System.IO;
using System.Reflection;
using UnityEditor;
using UnityEditor.TestTools.TestRunner.Api;
using UnityEngine;

namespace UnityTdd.TestDaemon
{
    [InitializeOnLoad]
    public static class TestDaemon
    {
        private const double FinishedStateHoldSeconds = 0.5d;

        private static DaemonState _state;
        private static string _currentFilter = string.Empty;
        private static DateTime _startedAtUtc;
        private static DateTime _finishedAtUtc;
        private static bool _cancelRequested;
        private static TestRunnerApi _currentApi;
        private static TestDaemonCallbacks _callbacks;

        static TestDaemon()
        {
            Initialize();
        }

        private static void Initialize()
        {
            TestDaemonProtocol.EnsureDirectory();
            RestoreState();

            EditorApplication.update -= Tick;
            EditorApplication.update += Tick;

            if (_state == DaemonState.Idle)
            {
                WriteStatus(DaemonState.Idle, "Waiting for run-tests.pending");
            }
        }

        private static void RestoreState()
        {
            _state = DaemonState.Idle;

            var persisted = TestDaemonProtocol.ReadStatus();
            if (persisted == null || string.IsNullOrEmpty(persisted.state))
            {
                return;
            }

            if (TryParseState(persisted.state, out var persistedState))
            {
                _state = persistedState;
            }

            _currentFilter = persisted.filter ?? string.Empty;
            _startedAtUtc = ParseUtc(persisted.startedAt);
            _finishedAtUtc = ParseUtc(persisted.finishedAt);
            _cancelRequested = persisted.cancelRequested;

            if (_state == DaemonState.Running)
            {
                _state = File.Exists(TestDaemonProtocol.PendingPath) ? DaemonState.Compiling : DaemonState.Idle;
            }
        }

        private static void Tick()
        {
            TestDaemonProtocol.EnsureDirectory();

            if (_state == DaemonState.Finished && (DateTime.UtcNow - _finishedAtUtc).TotalSeconds >= FinishedStateHoldSeconds)
            {
                WriteStatus(DaemonState.Idle, "Waiting for run-tests.pending");
            }

            if (_state == DaemonState.Running)
            {
                HandleCancelRequest();
                return;
            }

            if (!File.Exists(TestDaemonProtocol.PendingPath))
            {
                if (_state != DaemonState.Idle && !EditorApplication.isCompiling && !EditorApplication.isUpdating)
                {
                    WriteStatus(DaemonState.Idle, "Waiting for run-tests.pending");
                }

                return;
            }

            _currentFilter = TestDaemonProtocol.ReadFilter();

            if (EditorApplication.isCompiling)
            {
                WriteStatus(DaemonState.Compiling, "Waiting for script compilation");
                return;
            }

            if (EditorApplication.isUpdating)
            {
                WriteStatus(DaemonState.Refreshing, "Refreshing assets");
                return;
            }

            if (_state == DaemonState.Idle || _state == DaemonState.Finished)
            {
                RequestRefresh();
                return;
            }

            StartRun();
        }

        private static void RequestRefresh()
        {
            WriteStatus(DaemonState.Refreshing, "Refreshing assets");
            AssetDatabase.Refresh();
        }

        private static void StartRun()
        {
            _startedAtUtc = DateTime.UtcNow;
            _finishedAtUtc = default;
            _cancelRequested = false;

            TestDaemonProtocol.ResetEvents();
            TestDaemonProtocol.DeleteIfExists(TestDaemonProtocol.ResultsPath);
            TestDaemonProtocol.DeleteIfExists(TestDaemonProtocol.PendingPath);
            TestDaemonProtocol.DeleteIfExists(TestDaemonProtocol.CancelPath);

            WriteStatus(DaemonState.Running, "Executing Edit Mode tests");

            _callbacks = new TestDaemonCallbacks(_currentFilter, _startedAtUtc, () => _cancelRequested, OnRunFinished);
            _currentApi = ScriptableObject.CreateInstance<TestRunnerApi>();
            _currentApi.RegisterCallbacks(_callbacks);
            _currentApi.Execute(BuildExecutionSettings(_currentFilter));
        }

        private static void OnRunFinished(ResultsDocument results)
        {
            _finishedAtUtc = DateTime.UtcNow;
            WriteStatus(DaemonState.Finished, "Test run finished");

            if (_currentApi != null)
            {
                UnityEngine.Object.DestroyImmediate(_currentApi);
                _currentApi = null;
            }

            _callbacks = null;
        }

        private static void HandleCancelRequest()
        {
            if (!File.Exists(TestDaemonProtocol.CancelPath))
            {
                return;
            }

            TestDaemonProtocol.DeleteIfExists(TestDaemonProtocol.CancelPath);
            TestDaemonProtocol.AppendEvent(new EventDocument
            {
                @event = "cancelRequested"
            });

            _cancelRequested = true;
            WriteStatus(DaemonState.Running, "Cancel requested", true);
            InvokeCancel(_currentApi);
        }

        private static ExecutionSettings BuildExecutionSettings(string rawFilter)
        {
            var filter = new Filter
            {
                testMode = TestMode.EditMode
            };

            var directive = TestDaemonFilterParser.Parse(rawFilter);
            if (directive.HasValue)
            {
                TestDaemonFilterParser.Apply(filter, directive.Value);
            }

            return new ExecutionSettings(filter);
        }

        private static void WriteStatus(DaemonState state, string message, bool cancelRequested = false)
        {
            var now = DateTime.UtcNow;

            if (_state != state)
            {
                _state = state;
            }

            if (state == DaemonState.Idle)
            {
                _currentFilter = string.Empty;
                _startedAtUtc = default;
                _finishedAtUtc = default;
                _cancelRequested = false;
            }

            if (state == DaemonState.Running && _startedAtUtc == default)
            {
                _startedAtUtc = now;
            }

            if (state == DaemonState.Finished)
            {
                _finishedAtUtc = now;
            }

            TestDaemonProtocol.WriteStatus(new StatusDocument
            {
                state = ToStateString(state),
                startedAt = _startedAtUtc == default ? string.Empty : TestDaemonProtocol.ToUtcString(_startedAtUtc),
                updatedAt = TestDaemonProtocol.ToUtcString(now),
                finishedAt = _finishedAtUtc == default ? string.Empty : TestDaemonProtocol.ToUtcString(_finishedAtUtc),
                filter = _currentFilter ?? string.Empty,
                message = message ?? string.Empty,
                cancelRequested = cancelRequested || _cancelRequested
            });
        }

        private static void InvokeCancel(TestRunnerApi api)
        {
            if (api == null)
            {
                return;
            }

            var type = typeof(TestRunnerApi);
            var names = new[] { "CancelTestRun", "CancelAllTestRuns" };
            foreach (var methodName in names)
            {
                var method = type.GetMethod(methodName, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
                if (method != null && method.GetParameters().Length == 0)
                {
                    method.Invoke(api, null);
                    return;
                }

                method = type.GetMethod(methodName, BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic);
                if (method != null && method.GetParameters().Length == 0)
                {
                    method.Invoke(null, null);
                    return;
                }
            }
        }

        private static bool TryParseState(string rawState, out DaemonState state)
        {
            switch ((rawState ?? string.Empty).Trim().ToLowerInvariant())
            {
                case "idle":
                    state = DaemonState.Idle;
                    return true;
                case "refreshing":
                    state = DaemonState.Refreshing;
                    return true;
                case "compiling":
                    state = DaemonState.Compiling;
                    return true;
                case "running":
                    state = DaemonState.Running;
                    return true;
                case "finished":
                    state = DaemonState.Finished;
                    return true;
                default:
                    state = DaemonState.Idle;
                    return false;
            }
        }

        private static string ToStateString(DaemonState state)
        {
            switch (state)
            {
                case DaemonState.Refreshing:
                    return "refreshing";
                case DaemonState.Compiling:
                    return "compiling";
                case DaemonState.Running:
                    return "running";
                case DaemonState.Finished:
                    return "finished";
                default:
                    return "idle";
            }
        }

        private static DateTime ParseUtc(string rawValue)
        {
            if (string.IsNullOrWhiteSpace(rawValue))
            {
                return default;
            }

            if (DateTime.TryParse(rawValue, null, System.Globalization.DateTimeStyles.RoundtripKind, out var parsed))
            {
                return parsed.ToUniversalTime();
            }

            return default;
        }

        private enum DaemonState
        {
            Idle,
            Refreshing,
            Compiling,
            Running,
            Finished
        }
    }
}

using System;
using System.Reflection;
using UnityEditor;
using UnityEditor.TestTools.TestRunner.Api;
using UnityEngine;

namespace UnityTdd.TestDaemon
{
    public static class BatchmodeTestRunner
    {
        private static TestRunnerApi _api;
        private static TestDaemonCallbacks _callbacks;

        public static void Run()
        {
            var startedAtUtc = DateTime.UtcNow;
            var filter = TestDaemonProtocol.ReadFilter();

            try
            {
                TestDaemonProtocol.EnsureDirectory();
                TestDaemonProtocol.ResetEvents();
                TestDaemonProtocol.DeleteIfExists(TestDaemonProtocol.ResultsPath);
                TestDaemonProtocol.DeleteIfExists(TestDaemonProtocol.CancelPath);
                WriteStatus("running", startedAtUtc, default, filter, "Executing Edit Mode tests via Unity batchmode");

                _callbacks = new TestDaemonCallbacks(filter, startedAtUtc, () => false, results => OnRunFinished(results, startedAtUtc, filter));
                _api = ScriptableObject.CreateInstance<TestRunnerApi>();
                _api.RegisterCallbacks(_callbacks);
                _api.Execute(BuildExecutionSettings(filter));
            }
            catch (Exception exception)
            {
                WriteFailure(startedAtUtc, filter, "Batchmode test runner crashed before producing results.", exception.ToString());
                ScheduleExit(1);
            }
        }

        private static ExecutionSettings BuildExecutionSettings(string filterText)
        {
            var filter = new Filter
            {
                testMode = TestMode.EditMode
            };

            var directive = TestDaemonFilterParser.Parse(filterText);
            if (directive.HasValue)
            {
                TestDaemonFilterParser.Apply(filter, directive.Value);
            }

            SetBooleanMember(filter, "runSynchronously", true);

            var settings = new ExecutionSettings(filter);
            SetBooleanMember(settings, "runSynchronously", true);
            return settings;
        }

        private static void OnRunFinished(ResultsDocument results, DateTime startedAtUtc, string filter)
        {
            try
            {
                var finishedAtUtc = DateTime.UtcNow;
                WriteStatus("finished", startedAtUtc, finishedAtUtc, filter, results.failed > 0 ? "Test run finished with failures" : "Test run finished");
                ScheduleExit(results.failed > 0 ? 1 : 0);
            }
            finally
            {
                if (_api != null)
                {
                    UnityEngine.Object.DestroyImmediate(_api);
                    _api = null;
                }

                _callbacks = null;
            }
        }

        private static void ScheduleExit(int exitCode)
        {
            Debug.Log($"BatchmodeTestRunner calling EditorApplication.Exit({exitCode})");
            EditorApplication.Exit(exitCode);
        }



        private static void WriteFailure(DateTime startedAtUtc, string filter, string message, string stackTrace)
        {
            var finishedAtUtc = DateTime.UtcNow;
            TestDaemonProtocol.WriteResults(new ResultsDocument
            {
                state = "finished",
                total = 0,
                passed = 0,
                failed = 1,
                skipped = 0,
                duration = 0d,
                startedAt = TestDaemonProtocol.ToUtcString(startedAtUtc),
                finishedAt = TestDaemonProtocol.ToUtcString(finishedAtUtc),
                filter = filter ?? string.Empty,
                canceled = false,
                failures = new[]
                {
                    new FailureDocument
                    {
                        name = "BatchmodeTestRunner",
                        message = message ?? string.Empty,
                        stackTrace = stackTrace ?? string.Empty
                    }
                }
            });

            TestDaemonProtocol.AppendEvent(new EventDocument
            {
                @event = "runFinished",
                status = "failed",
                message = message ?? string.Empty
            });

            WriteStatus("finished", startedAtUtc, finishedAtUtc, filter, message);
        }

        private static void WriteStatus(string state, DateTime startedAtUtc, DateTime finishedAtUtc, string filter, string message)
        {
            TestDaemonProtocol.WriteStatus(new StatusDocument
            {
                state = state ?? "idle",
                startedAt = startedAtUtc == default ? string.Empty : TestDaemonProtocol.ToUtcString(startedAtUtc),
                updatedAt = TestDaemonProtocol.ToUtcString(DateTime.UtcNow),
                finishedAt = finishedAtUtc == default ? string.Empty : TestDaemonProtocol.ToUtcString(finishedAtUtc),
                filter = filter ?? string.Empty,
                message = message ?? string.Empty,
                cancelRequested = false
            });
        }

        private static void SetBooleanMember(object target, string memberName, bool value)
        {
            var type = target.GetType();
            var field = type.GetField(memberName, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            if (field != null && field.FieldType == typeof(bool))
            {
                field.SetValue(target, value);
                return;
            }

            var property = type.GetProperty(memberName, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            if (property != null && property.CanWrite && property.PropertyType == typeof(bool))
            {
                property.SetValue(target, value, null);
            }
        }
    }
}

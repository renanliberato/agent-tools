using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using UnityEditor.TestTools.TestRunner.Api;

namespace UnityTdd.TestDaemon
{
    public sealed class TestDaemonCallbacks : ICallbacks
    {
        private readonly string _filter;
        private readonly DateTime _startedAtUtc;
        private readonly Func<bool> _isCanceled;
        private readonly Action<ResultsDocument> _onFinished;

        public TestDaemonCallbacks(string filter, DateTime startedAtUtc, Func<bool> isCanceled, Action<ResultsDocument> onFinished)
        {
            _filter = filter ?? string.Empty;
            _startedAtUtc = startedAtUtc;
            _isCanceled = isCanceled;
            _onFinished = onFinished;
        }

        public void RunStarted(ITestAdaptor testsToRun)
        {
            TestDaemonProtocol.AppendEvent(new EventDocument
            {
                @event = "runStarted"
            });
        }

        public void RunFinished(ITestResultAdaptor result)
        {
            var finishedAtUtc = DateTime.UtcNow;
            var results = TestResultSummaryBuilder.Build(result, _startedAtUtc, finishedAtUtc, _filter, _isCanceled != null && _isCanceled());

            TestDaemonProtocol.WriteResults(results);
            TestDaemonProtocol.AppendEvent(new EventDocument
            {
                @event = "runFinished",
                status = results.canceled ? "canceled" : (results.failed > 0 ? "failed" : "passed")
            });

            _onFinished?.Invoke(results);
        }

        public void TestStarted(ITestAdaptor test)
        {
            if (TestResultSummaryBuilder.HasChildren(test))
            {
                return;
            }

            TestDaemonProtocol.AppendEvent(new EventDocument
            {
                @event = "testStarted",
                name = TestResultSummaryBuilder.GetDisplayName(test)
            });
        }

        public void TestFinished(ITestResultAdaptor result)
        {
            if (TestResultSummaryBuilder.HasChildren(result))
            {
                return;
            }

            TestDaemonProtocol.AppendEvent(new EventDocument
            {
                @event = "testFinished",
                name = TestResultSummaryBuilder.GetDisplayName(result),
                status = TestResultSummaryBuilder.GetStatus(result)
            });
        }
    }

    public static class TestResultSummaryBuilder
    {
        public static ResultsDocument Build(ITestResultAdaptor root, DateTime startedAtUtc, DateTime finishedAtUtc, string filter, bool canceled)
        {
            var leafResults = new List<ITestResultAdaptor>();
            CollectLeafResults(root, leafResults);

            var failures = new List<FailureDocument>();
            var passed = 0;
            var failed = 0;
            var skipped = 0;

            foreach (var leafResult in leafResults)
            {
                var status = GetStatus(leafResult);
                switch (status)
                {
                    case "passed":
                        passed++;
                        break;
                    case "failed":
                        failed++;
                        failures.Add(new FailureDocument
                        {
                            name = GetDisplayName(leafResult),
                            message = GetStringProperty(leafResult, "Message"),
                            stackTrace = GetStringProperty(leafResult, "StackTrace")
                        });
                        break;
                    default:
                        skipped++;
                        break;
                }
            }

            return new ResultsDocument
            {
                state = "finished",
                total = leafResults.Count,
                passed = passed,
                failed = failed,
                skipped = skipped,
                duration = GetDuration(root, leafResults),
                startedAt = TestDaemonProtocol.ToUtcString(startedAtUtc),
                finishedAt = TestDaemonProtocol.ToUtcString(finishedAtUtc),
                filter = filter ?? string.Empty,
                canceled = canceled,
                failures = failures.ToArray()
            };
        }

        public static bool HasChildren(object node)
        {
            var hasChildrenProperty = node.GetType().GetProperty("HasChildren");
            if (hasChildrenProperty != null && hasChildrenProperty.PropertyType == typeof(bool))
            {
                return (bool)hasChildrenProperty.GetValue(node, null);
            }

            var childrenProperty = node.GetType().GetProperty("Children");
            if (childrenProperty == null)
            {
                return false;
            }

            var enumerable = childrenProperty.GetValue(node, null) as IEnumerable;
            if (enumerable == null)
            {
                return false;
            }

            foreach (var _ in enumerable)
            {
                return true;
            }

            return false;
        }

        public static string GetDisplayName(object node)
        {
            var fullName = GetStringProperty(node, "FullName");
            if (!string.IsNullOrEmpty(fullName))
            {
                return fullName;
            }

            return GetStringProperty(node, "Name");
        }

        public static string GetStatus(ITestResultAdaptor result)
        {
            var testStatus = GetStringProperty(result, "TestStatus");
            if (!string.IsNullOrEmpty(testStatus))
            {
                return NormalizeStatus(testStatus);
            }

            var resultStateProperty = result.GetType().GetProperty("ResultState");
            if (resultStateProperty != null)
            {
                var resultState = resultStateProperty.GetValue(result, null);
                if (resultState != null)
                {
                    var statusProperty = resultState.GetType().GetProperty("Status");
                    if (statusProperty != null)
                    {
                        var statusValue = statusProperty.GetValue(resultState, null);
                        if (statusValue != null)
                        {
                            return NormalizeStatus(statusValue.ToString());
                        }
                    }

                    return NormalizeStatus(resultState.ToString());
                }
            }

            return "skipped";
        }

        private static void CollectLeafResults(ITestResultAdaptor node, ICollection<ITestResultAdaptor> results)
        {
            if (!HasChildren(node))
            {
                results.Add(node);
                return;
            }

            var children = node.GetType().GetProperty("Children")?.GetValue(node, null) as IEnumerable;
            if (children == null)
            {
                results.Add(node);
                return;
            }

            foreach (var child in children)
            {
                if (child is ITestResultAdaptor childResult)
                {
                    CollectLeafResults(childResult, results);
                }
            }
        }

        private static double GetDuration(ITestResultAdaptor root, List<ITestResultAdaptor> leafResults)
        {
            var rawDuration = GetNumericProperty(root, "Duration");
            if (rawDuration.HasValue)
            {
                return rawDuration.Value;
            }

            double total = 0d;
            foreach (var leaf in leafResults)
            {
                var leafDuration = GetNumericProperty(leaf, "Duration");
                if (leafDuration.HasValue)
                {
                    total += leafDuration.Value;
                }
            }

            return total;
        }

        private static double? GetNumericProperty(object instance, string propertyName)
        {
            var property = instance.GetType().GetProperty(propertyName);
            if (property == null)
            {
                return null;
            }

            var value = property.GetValue(instance, null);
            if (value == null)
            {
                return null;
            }

            return Convert.ToDouble(value, CultureInfo.InvariantCulture);
        }

        private static string GetStringProperty(object instance, string propertyName)
        {
            var property = instance.GetType().GetProperty(propertyName);
            if (property == null)
            {
                return string.Empty;
            }

            var value = property.GetValue(instance, null);
            return value?.ToString() ?? string.Empty;
        }

        private static string NormalizeStatus(string rawStatus)
        {
            var normalized = (rawStatus ?? string.Empty).Trim().ToLowerInvariant();
            if (normalized.Contains("pass") || normalized.Contains("success"))
            {
                return "passed";
            }

            if (normalized.Contains("fail") || normalized.Contains("error"))
            {
                return "failed";
            }

            return "skipped";
        }
    }
}

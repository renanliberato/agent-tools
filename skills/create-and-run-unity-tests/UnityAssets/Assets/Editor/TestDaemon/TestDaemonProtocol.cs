using System;
using System.IO;
using System.Text;
using UnityEngine;

namespace UnityTdd.TestDaemon
{
    [Serializable]
    public sealed class StatusDocument
    {
        public string state = "idle";
        public string startedAt = string.Empty;
        public string updatedAt = string.Empty;
        public string finishedAt = string.Empty;
        public string filter = string.Empty;
        public string message = string.Empty;
        public bool cancelRequested;
    }

    [Serializable]
    public sealed class FailureDocument
    {
        public string name = string.Empty;
        public string message = string.Empty;
        public string stackTrace = string.Empty;
    }

    [Serializable]
    public sealed class ResultsDocument
    {
        public string state = "finished";
        public int total;
        public int passed;
        public int failed;
        public int skipped;
        public double duration;
        public string startedAt = string.Empty;
        public string finishedAt = string.Empty;
        public string filter = string.Empty;
        public bool canceled;
        public FailureDocument[] failures = Array.Empty<FailureDocument>();
    }

    [Serializable]
    public sealed class EventDocument
    {
        public string @event = string.Empty;
        public string name = string.Empty;
        public string status = string.Empty;
        public string timestamp = string.Empty;
        public string message = string.Empty;
    }

    public static class TestDaemonProtocol
    {
        public const string RootRelativePath = "Library/TestDaemon";

        private static readonly UTF8Encoding Utf8NoBom = new UTF8Encoding(false);

        public static string RootPath => Path.GetFullPath(RootRelativePath);

        public static string PendingPath => Path.Combine(RootPath, "run-tests.pending");

        public static string FilterPath => Path.Combine(RootPath, "run-tests.filter");

        public static string CancelPath => Path.Combine(RootPath, "run-tests.cancel");

        public static string StatusPath => Path.Combine(RootPath, "status.json");

        public static string ResultsPath => Path.Combine(RootPath, "results.json");

        public static string EventsPath => Path.Combine(RootPath, "events.ndjson");

        public static void EnsureDirectory()
        {
            Directory.CreateDirectory(RootPath);
        }

        public static StatusDocument ReadStatus()
        {
            if (!File.Exists(StatusPath))
            {
                return null;
            }

            try
            {
                return JsonUtility.FromJson<StatusDocument>(File.ReadAllText(StatusPath, Utf8NoBom));
            }
            catch
            {
                return null;
            }
        }

        public static string ReadFilter()
        {
            if (!File.Exists(FilterPath))
            {
                return string.Empty;
            }

            return File.ReadAllText(FilterPath, Utf8NoBom).Trim();
        }

        public static void WriteStatus(StatusDocument status)
        {
            WriteJson(StatusPath, status);
        }

        public static void WriteResults(ResultsDocument results)
        {
            WriteJson(ResultsPath, results);
        }

        public static void ResetEvents()
        {
            EnsureDirectory();
            File.WriteAllText(EventsPath, string.Empty, Utf8NoBom);
        }

        public static void AppendEvent(EventDocument eventDocument)
        {
            EnsureDirectory();
            eventDocument.timestamp = ToUtcString(DateTime.UtcNow);
            var line = JsonUtility.ToJson(eventDocument);
            File.AppendAllText(EventsPath, line + Environment.NewLine, Utf8NoBom);
        }

        public static void DeleteIfExists(string path)
        {
            if (File.Exists(path))
            {
                File.Delete(path);
            }
        }

        public static string ToUtcString(DateTime value)
        {
            return value.ToUniversalTime().ToString("O");
        }

        private static void WriteJson<T>(string path, T document)
        {
            EnsureDirectory();

            var tempPath = path + ".tmp";
            var json = JsonUtility.ToJson(document, true) + Environment.NewLine;

            File.WriteAllText(tempPath, json, Utf8NoBom);

            if (File.Exists(path))
            {
                File.Copy(tempPath, path, true);
                File.Delete(tempPath);
                return;
            }

            File.Move(tempPath, path);
        }
    }
}

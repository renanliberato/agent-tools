using System;
using System.Reflection;
using UnityEditor.TestTools.TestRunner.Api;

namespace UnityTdd.TestDaemon
{
    public enum FilterDirectiveKind
    {
        Assembly,
        Namespace,
        Fixture,
        Test
    }

    public struct FilterDirective
    {
        public FilterDirective(FilterDirectiveKind kind, string value)
        {
            Kind = kind;
            Value = value ?? string.Empty;
        }

        public FilterDirectiveKind Kind { get; }

        public string Value { get; }
    }

    public static class TestDaemonFilterParser
    {
        public static FilterDirective? Parse(string raw)
        {
            var value = (raw ?? string.Empty).Trim();
            if (value.Length == 0)
            {
                return null;
            }

            if (TryParseExplicit(value, out var explicitDirective))
            {
                return explicitDirective;
            }

            return new FilterDirective(InferKind(value), value);
        }

        public static void Apply(Filter filter, FilterDirective directive)
        {
            switch (directive.Kind)
            {
                case FilterDirectiveKind.Assembly:
                    SetStringArray(filter, directive.Value, "assemblyNames");
                    break;
                case FilterDirectiveKind.Namespace:
                case FilterDirectiveKind.Fixture:
                    SetStringArray(filter, directive.Value, "groupNames");
                    break;
                case FilterDirectiveKind.Test:
                    SetStringArray(filter, directive.Value, "testNames");
                    break;
                default:
                    throw new ArgumentOutOfRangeException(nameof(directive.Kind), directive.Kind, "Unsupported filter directive.");
            }
        }

        private static bool TryParseExplicit(string value, out FilterDirective directive)
        {
            directive = default;

            var separatorIndex = value.IndexOf(':');
            if (separatorIndex <= 0 || separatorIndex >= value.Length - 1)
            {
                return false;
            }

            var prefix = value.Substring(0, separatorIndex).Trim().ToLowerInvariant();
            var payload = value.Substring(separatorIndex + 1).Trim();
            if (payload.Length == 0)
            {
                return false;
            }

            switch (prefix)
            {
                case "assembly":
                    directive = new FilterDirective(FilterDirectiveKind.Assembly, payload);
                    return true;
                case "namespace":
                    directive = new FilterDirective(FilterDirectiveKind.Namespace, payload);
                    return true;
                case "fixture":
                    directive = new FilterDirective(FilterDirectiveKind.Fixture, payload);
                    return true;
                case "test":
                    directive = new FilterDirective(FilterDirectiveKind.Test, payload);
                    return true;
                default:
                    return false;
            }
        }

        private static FilterDirectiveKind InferKind(string value)
        {
            if (value.IndexOf('.') < 0)
            {
                return FilterDirectiveKind.Fixture;
            }

            if (IsAssemblyName(value))
            {
                return FilterDirectiveKind.Assembly;
            }

            var segments = value.Split(new[] { '.' }, StringSplitOptions.RemoveEmptyEntries);
            if (segments.Length >= 2 && IsFixtureName(segments[segments.Length - 2]))
            {
                return FilterDirectiveKind.Test;
            }

            if (IsFixtureName(segments[segments.Length - 1]))
            {
                return FilterDirectiveKind.Fixture;
            }

            return FilterDirectiveKind.Namespace;
        }

        private static bool IsAssemblyName(string value)
        {
            return value.EndsWith(".Tests", StringComparison.OrdinalIgnoreCase)
                || value.EndsWith(".Test", StringComparison.OrdinalIgnoreCase)
                || value.EndsWith(".EditorTests", StringComparison.OrdinalIgnoreCase)
                || value.EndsWith(".PlayModeTests", StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsFixtureName(string value)
        {
            return value.EndsWith("Tests", StringComparison.OrdinalIgnoreCase)
                || value.EndsWith("Test", StringComparison.OrdinalIgnoreCase);
        }

        private static void SetStringArray(Filter filter, string value, string memberName)
        {
            var values = new[] { value };
            var type = filter.GetType();

            var field = type.GetField(memberName, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            if (field != null)
            {
                field.SetValue(filter, values);
                return;
            }

            var property = type.GetProperty(memberName, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            if (property != null && property.CanWrite)
            {
                property.SetValue(filter, values, null);
                return;
            }

            throw new MissingMemberException(type.FullName, memberName);
        }
    }
}

using SharpEmu.Diagnostics.Contracts;

namespace SharpEmu.Diagnostics
{
    public class SignalSafeCrashWriter : ICrashDiagnosticSource
    {
        public static SignalSafeCrashWriter Instance { get; } = new();
        public void QueueCrash(string signalType, ulong faultAddress, ulong rip, in RegisterSnapshot registers) { }
    }
}

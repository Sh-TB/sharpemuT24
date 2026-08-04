// EXP-036: Synchronization call tracer for HLE handlers.
//
// This class lives in SharpEmu.Libs (not SharpEmu.Core) so HLE handlers
// can call it without a project reference. It uses a static delegate
// that DirectExecutionBackend sets up via reflection.
//
// The delegate signature matches DirectExecutionBackend.Exp036RecordSyncCall:
//   void Record(string funcName, ulong callerRip, int tid,
//               ulong arg1, ulong arg2, ulong arg3, ulong retVal)

using System;

namespace SharpEmu.Libs.Kernel;

public static class _Exp036SyncTrace
{
    public delegate void RecordDelegate(
        string funcName, ulong callerRip, int tid,
        ulong arg1, ulong arg2, ulong arg3, ulong retVal);

    private static RecordDelegate? _recorder;

    public static void SetRecorder(RecordDelegate? recorder)
    {
        _recorder = recorder;
    }

    public static void Record(
        string funcName, ulong callerRip, int tid,
        ulong arg1, ulong arg2, ulong arg3, ulong retVal)
    {
        _recorder?.Invoke(funcName, callerRip, tid, arg1, arg2, arg3, retVal);
    }
}

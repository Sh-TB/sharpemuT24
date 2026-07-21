# تحلیل کامل تاریخچه چت - SharpEmu Linux Port

## 📊 خلاصه وضعیت فعلی

### بازی‌های تست شده:
| بازی | ID | وضعیت Boot | Imports | صفحه لود |
|------|-----|-----------|---------|----------|
| Arise: A Simple Story | PPSA06328 | ✅ Exit Code 0 | 1,084 | ❌ |
| HellGunner | PPSA06998 | ✅ Boot شد | ~15 | ❌ |
| Unity Game | PPSA14677 | ✅ Boot شد | 968 | ❌ |
| Dreaming Sarah | PPSA02929 | در حال تست | - | ❌ |

### 🎯 هدف اصلی که **هرگز** достиг نشده:
> **عکس از صفحه بوت/لود بازی**

---

## 🔴 مشکلات بحرانی که مانع رسیدن به صفحه لود هستند:

### ۱. Signal Handler کرش‌ها را پنهان می‌کند
**وضعیت فعلی:**
```
Guest → SIGSEGV → Signal Handler → Instruction Skip / Zero Page → Continue
```
**مشکل:** اگر NULL از TLS آمده باشد، هیچ‌وقت متوجه نمی‌شویم. بازی ۵۰۰۰ دستور بعد ترکید.
**راه‌حل:** Signal Handler فقط باید Context را ثبت کند و Exception به Runtime تحویل دهد.

### ۲. PTTLS ناقص (محتمل‌ترین علت NULL deref)
**Sequence اجرایی:**
```
pthread_key_create → pthread_setspecific → scePthreadSelf → NULL
```
این Pattern یعنی TLS Block یا TCB یا DTV کامل نیست.

### ۳. HLE Stubها فقط Success برمی‌گردانند
**مثال خطرناک:**
```csharp
// pthread_once باید Once Control واقعی را پیاده کند
// نه فقط return 0;
public static int PthreadOnce() => 0; // ❌ خطرناک!
```

### ۴. Import Side Effects پیاده‌سازی نشده
**مثال:**
```csharp
// pthread_setspecific نباید فقط Success برگرداند
// باید Thread → TLS → Key → Value را ذخیره کند
```

### ۵. GPU Memory Mapping ناقص
**Crash RIP برای PPSA06328:** `0x...170FB2`  
**Crash fault:** `0x1FE000000` (GPU placeholder)  
**معنی:** بازی به جای حافظه GPU واقعی به placeholder ما رسیده.

---

## ✅ موفقیت‌های قبلی (۷۴+ تلاش):

### تغییرات کلیدی Linux Port:

| # | تغییر | فایل | اهمیت |
|---|-------|------|-------|
| ۱ | mmap/mprotect به جای VirtualAlloc | NativeMemoryInterop.cs | حیاتی |
| ۲ | pthread به جای CreateThread | NativeThreadInterop.cs | حیاتی |
| ۳ | Calling Convention Shims | NativeFunctionResolver.cs | حیاتی |
| ۴ | Signal Handler با FS save/restore | GuestRunner.c | حیاتی |
| ۵ | mmap(MAP_FIXED) bug fix | PhysicalVirtualMemory.cs | **بزرگ‌ترین کشف** |
| ۶ | TLS canary fix | CpuDispatcher.cs | مهم |
| ۷ | DT_INIT patch | DirectExecutionBackend.cs | مهم |
| ۸ | Diagnostic Event Bus | SharpEmu.Logging | جدید |

### پیشرفت HLE Imports:
```
libc:
  ✅ _init_env
  ✅ atexit (x2)
  ✅ vsnprintf (x2)
  ✅ printf (x2)

libKernel:
  ✅ sceKernelGetDirectMemorySize
  ✅ sceKernelAllocateDirectMemory
  ✅ sceKernelMapDirectMemory
  ✅ pthread_once
  ✅ pthread_key_create
  ✅ pthread_setspecific
  ✅ scePthreadSelf (x2)

❌ sceVideoOutOpen (هرگز نرسیده!)
```

---

## 🚧 کارهای انجام شده در این جلسه:

### Virtual Vulkan Backend / Headless Presenter:
✅ Stage 1: Force Headless Mode (`SHARPEMU_HEADLESS=1`)  
✅ Stage 2: VideoOutManager به عنوان مالک تصمیم  
✅ Stage 3: Fake Display با handle معتبر  
✅ Stage 4: Frame Metadata JSON  
✅ Stage 5: AGC Command Recorder  
✅ Stage 6: DiagnosticEngine Integration  

**مشکل:** این همه چیز خوب است، اما اگر بازی هرگز به `sceVideoOutOpen` نرسد، هیچ فریمی capture نخواهد شد!

---

## 🎯 برنامه اقدام برای رسیدن به هدف:

### Phase 1: رفع مشکلات بحرانی (اولویت بالا)

#### ۱.۱ اصلاح Signal Handler
```csharp
// فعلی: Skip instruction و ادامه (❌ پنهان کردن crash)
// مورد نیاز: فقط ثبت context و throw exception (✅ دیباگ صحیح)
```

#### ۱.۲ پیاده‌سازی PT_TLS Template
```csharp
// پیدا کردن PT_TLS segment در program headers
// تخصیص TLS block با alignment درست
// copy کردن .tdata template
// zero-fill کردن .tbss
// تنظیم FS register به TLS base
```

#### ۱.³ پیاده‌سازی HLE Functions به درستی
```csharp
// pthread_once → Once Control واقعی
// pthread_setspecific → ذخیره در TLS
// scePthreadSelf → برگرداندن thread ID واقعی
```

### Phase 2: GPU Memory Mapping

#### ۲.۱ Placeholder به Real Mapping
```
0x1FE000000 → حافظه واقعی (نه placeholder)
```

#### ۲.۲ رسیدن به sceVideoOutOpen
```
اگر Phase 1 موفق باشد، بازی باید به اینجا برسد
```

### Phase 3: Capture فریم با Headless Presenter

#### ۳.۱ فعال‌سازی SHARPEMU_HEADLESS=1
#### ۳.۲ دریافت اولین فریم
#### ۳.۳ تبدیل به PNG برای نمایش

---

## 📁 فایل‌های کلیدی که باید بررسی/اصلاح شوند:

### فایل‌های بحرانی:
1. `src/SharpEmu.Core/Cpu/Native/GuestRunner.c` - Signal Handler
2. `src/SharpEmu.Core/Cpu/CpuDispatcher.cs` - TLS Setup
3. `src/SharpEmu.Core/Memory/PhysicalVirtualMemory.cs` - Memory Mapping
4. `src/SharpEmu.Libs/VideoOut/VideoOutExports.cs` - sceVideoOutOpen
5. `src/SharpEmu.Libs/Kernel/PthreadCompatExports.cs` - Thread Functions

### فایل‌های جدید این جلسه:
1. `src/SharpEmu.Libs/VideoOut/VideoOutManager.cs` - Backend Selection
2. `src/SharpEmu.Libs/VideoOut/HeadlessVideoPresenter.cs` - Frame Capture
3. `src/SharpEmu.CLI/DiagnosticEngine.cs` - GPU Diagnostics

---

## 🔬 Evidence Chain از Crash Reports:

### PPSA06328 (Arise):
```
Import call sites: 1,084
Boot stages: SelfImage → EntryPoint ✓
VideoOut: ✗
Crash RIP: 0x...170FB2
Crash fault: 0x1FE000000 (GPU placeholder)
HLE modules: 35, همه 100%
```

### PPSA14677 (Unity):
```
Import call sites: 968
Boot stages: SelfImage → EntryPoint ✓
VideoOut: ✗
Crash RIP: 0x...07F33FE
Crash fault: 0x1836 (NULL deref)
HLE modules: 12, همه 100%
```

---

## 💡 نتیجه‌گیری کلیدی:

> **"این پروژه از نظر معماری به مرحله‌ای رسیده که مشکل اصلی دیگر 'پورت لینوکس' نیست."**

سه موضوع تعیین می‌کنند که بازی بوت می‌شود یا نه:
1. **درستی کامل TLS (PT_TLS)**
2. **صحت کامل ABI**
3. **وابستگی زیاد به Hackها** (Zero Page, Instruction Skip)

---

## 📝 دستورالعمل ادامه کار:

### قدم ۱: بررسی فایل‌های فعلی
```bash
# خواندن GuestRunner.c برای درک Signal Handler
# خواندن CpuDispatcher.cs برای درک TLS setup
# خواندن VideoOutExports.cs برای درک sceVideoOutOpen
```

### قدم ۲: اصلاح Signal Handler
```csharp
// فقط log کردن، نه skip کردن instruction
```

### قدم ۳: پیاده‌سازی PT_TLS
```csharp
// پیدا کردن و پردازش PT_TLS segment
```

### قدم ۴: تست با Dreaming Sarah
```bash
export SHARPEMU_HEADLESS=1
dotnet run -- --boot eboot.bin
```

### قدم ۵:捕获 اولین فریم
```bash
ls -la ./SharpEmu/headless_frames/
```

---

## 🎮 انتظار کاربر:

> "هدف بوت کامل است. هر خطایی که پیدا کردی، آن را حل کن. وقتی عکس بوت را گرفتی، یک فایل MD کلی از تمام تغییرات بده."

**نکته مهم:** کاربر خسته از:
- سوال‌پرسی مداوم
- لیست‌های کاری بدون انجام کار
- پایان جلسه بدون رسیدن به هدف
- عدم ارائه فایل ZIP/Fork نهایی

---

*تاریخ ایجاد: 2026-01-17*
*بر اساس تحلیل 32,649 خط تاریخچه چت*

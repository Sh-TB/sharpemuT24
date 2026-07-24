# SharpEmu T24 — Final Release Report

## ساختار نهایی

### بازی‌های تست شده

| # | بازی | TitleID | موتور | وضعیت | عکس |
|---|------|---------|-------|-------|-----|
| 1 | Dreaming Sarah | PPSA02929 | Native C++ | ✅ فریم واقعی | dreaming-sarah-last.png (۱۶۷ رنگ) |
| 2 | Yatzi | PPSA17697 | Unity IL2CPP | ❌ VkqLPArfFdc NID حل‌نشده | — |
| 3 | Seeker My Shadow | PPSA12500 | Unity IL2CPP | ❌ VkqLPArfFdc NID حل‌نشده | — |
| 4 | Arise | PPSA06328 | Native C++ | ❌ SIGILL crash | — |
| 5 | Harvest Days | PPSA14677 | Unity IL2CPP | ❌ فایل‌های PRX رمزنگاری‌شده | — |

### ابزارهای دیاگنوستیک ساخته شده

1. **BootDependencyAnalyzer** — بررسی فایل‌های لازم بازی قبل از اجرای CPU
2. **ExecutableFormatDetector** — تشخیص ELF/SELF/fSELF برای هر فایل اجرایی
3. **FrameAnalyzer** — تحلیل فریم خروجی (splash تک‌رنگ vs محتوای واقعی)
4. **SHARPEMU_LOG_SEMA** — لاگ کامل semaphore operations
5. **SHARPEMU_LOG_OPEN** — لاگ file open/close
6. **SHARPEMU_LOG_IL2CPP_NULL** — لاگ IL2CPP stubs که NULL برمی‌گردانند
7. **SHARPEMU_TRACE_GUEST_IMAGES** — dump فریم‌های Vulkan swapchain
8. **SHARPEMU_DUMP_VIDEOOUT** — dump فریم‌های VideoOut به BMP
9. **SHARPEMU_SWAPCHAIN_DUMP_EVERY** — dump دوره‌ای swapchain
10. **SHARPEMU_STALL_WATCHDOG_SECONDS** — تشخیص stall در اجرای guest

### اشتباهات کلیدی (که چند روز وقت گرفت)

1. **الگوی تست HSV به جای خروجی بازی** — HeadlessVideoPresenter.GenerateFramePattern() رنگ RGB(229,95,68) = HSV(10°,0.7,0.9) تولید می‌کرد که با "splash Unity" اشتباه گرفته شد. این فقط الگوی تست بود.

2. **فرضیه‌های غلط که رد شدند:**
   - ❌ Scheduler pump مشکل دارد (READY همیشه 0 بود، pump چیزی برای اجرا نداشت)
   - ❌ Semaphore deadlock (۴۸۳۱ سیگنال رخ داد، بن‌بست نبود)
   - ❌ Metadata خراب است (entropy 5.54، معتبر بود)
   - ❌ فایل‌های ناقص (Seeker همه فایل‌ها را داشت)
   - ❌ GPU stub مشکل دارد (بازی از fake stubs استفاده نمی‌کرد)
   - ❌ Regression بین v0.0.3 و HEAD (هر دو فریم سیاه داشتند)

3. **مشکل واقعی (که حل شد):** تابع `PreferX11OnLinuxWayland()` فقط وقتی `WAYLAND_DISPLAY` تنظیم شده بود، X11 را اجباری می‌کرد. روی Xvfb-only Linux (بدون Wayland)، GLFW پلتفرم را تشخیص نمی‌داد و خطای `65550: Failed to detect any supported platform` می‌داد. Fix: همیشه وقتی `DISPLAY` تنظیم است، X11 را اجباری کن (PR #457).

4. **مشکل باقی‌مانده برای بازی‌های Unity IL2CPP:** NID `VkqLPArfFdc` حل‌نشده. این تابع در bootstrap IL2CPP فراخوانی می‌شود، SharpEmu آن را پیاده‌سازی نکرده، NULL برمی‌گرداند، بازی از طریق NULL فراخوانی می‌کند و در crash-recover loop گیر می‌کند. در بازی Native (Dreaming Sarah) این NID فراخوانی نمی‌شود.

### محیط اجرا
- OS: Debian Linux (headless, no physical GPU)
- Display: Xvfb :99 1920x1080x24
- Vulkan: Lavapipe (llvmpipe, LLVM 19.1.7, software rasterizer)
- .NET SDK: 10.0.302
- GLFW: 3.4 (with X11 platform hint)
- X11 libs: libX11, libxcb, libxkbcommon (user-local install)

### دستور اجرا
```bash
export VK_ICD_FILENAMES=lvp_icd.json
export DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/xdg
export LD_LIBRARY_PATH=...
unset SHARPEMU_HEADLESS
export SHARPEMU_TRACE_GUEST_IMAGES=present
export SHARPEMU_GUEST_IMAGE_DUMP_DIR=/tmp/framebuffers
./SharpEmu --log-level=info eboot.bin
```

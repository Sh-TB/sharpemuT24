# SharpEmuT24 Agent Master Rules

**Purpose:** The single permanent file every agent MUST read at the start of every session, before any code change, debug, test, or architecture decision.

**Companion documents:**
- `docs/AGENT_CORE_RULES.md` — 6 Golden Rules (detailed version)
- `docs/SOP/SHARPEMU_DEBUG_PROTOCOL.md` — Full 15-rule SOP
- `.agent_state/` — Investigation memory (current_state, known_facts, closed_paths, experiment_history, next_actions)

---

## بخش 1 — قوانین اصلی (همیشه باید خوانده و رعایت شود)

این فایل باید قبل از هر تغییر کد، دیباگ، تست یا تصمیم معماری خوانده شود.

### 6 Golden Rules (قوانین طلایی دائمی)

#### Rule 1 — Golden Test First (مهم‌ترین قانون)

قبل از هر تغییر:
- تست‌های Golden موجود باید بررسی شوند.
- هر بازی که قبلاً PASS شده، دیگر فرضیه نیست؛ Fact تایید شده است.
- چیزی که قبلاً اجرا شده را نباید دوباره به عنوان «احتمال» گزارش کرد.

مثال — Dreaming Sarah:

❌ اشتباه:
```
احتمال اجرا 70-80%
```

✅ صحیح:
```
Dreaming Sarah = CONFIRMED GOLDEN BASELINE
```

هر تغییر باید بررسی کند:
- آیا Golden Test خراب شده؟
- آیا رفتار قبلی حفظ شده؟

#### Rule 2 — GitHub Commit Required

هیچ کاری کامل نیست مگر اینکه:
1. تغییرات commit شوند.
2. Push شوند.
3. لینک GitHub ارائه شود.
4. نتیجه commit گزارش شود.

فرمت گزارش:
```
Commit:
Hash:
Files Changed:
GitHub URL:
HTTP Status:
```

اگر نتوان push کرد:
- باید دلیل دقیق نوشته شود.

#### Rule 3 — Runtime Test Over Static Guess

هیچ نتیجه‌ای بدون تست واقعی اعلام نشود.

سه سطح نتیجه:
- **PASS** — تست اجرا شده و موفق بوده.
- **FAIL** — تست اجرا شده و شکست خورده.
- **BLOCKED** — امکان تست وجود نداشته.

مثال:

❌
```
احتمالا مشکل حل شده
```

✅
```
Static verification PASS
Runtime validation BLOCKED (missing dotnet SDK)
```

#### Rule 4 — Suspicious Issue = Immediate Test

اگر در هر مرحله مورد مشکوکی دیده شد:
- نباید فقط ثبت شود.
- باید همان لحظه:
  1. یک فرضیه ساخته شود.
  2. تست کوچک نوشته شود.
  3. نتیجه ثبت شود.

چرخه:
```
Observation
 ↓
Hypothesis
 ↓
Minimal Test
 ↓
Evidence
 ↓
Decision
```

#### Rule 5 — Existing Diagnostics First

قبل از ساخت Debug جدید، سیستم‌های موجود باید بررسی شوند.

اول استفاده:
- DebugIntelligenceEngine
- Guest Call Stack
- HLE Debugger
- Missing Function Tracker
- Memory Fault Analyzer
- Resolver Trace
- Frame Capture
- Crash Analyzer

قانون: **New Debug Code = Last Option**

#### Rule 6 — No Re-investigation of Closed Paths

مسیرهایی که قبلاً بررسی و رد شده‌اند:
- نباید دوباره بررسی شوند مگر با Evidence جدید.

قبل از شروع Investigation، خواندن:
- `.agent_state/closed_paths.md`
- `.agent_state/known_facts.md`
- `.agent_state/experiment_history.json`

---

## بخش 2 — قوانین دوره‌ای (هر چند وقت یکبار یادآوری شود)

این بخش را Agent هر چند Session یکبار دوباره بخواند.

### SHARPEMU_DEBUG_PROTOCOL

#### 1. Evidence First
هر ادعا باید یکی از این‌ها داشته باشد:
- Log
- Test result
- Code reference
- Commit

#### 2. Experiment Numbering
هر Investigation: `EXP-XXX`

ساختار:
```
EXP-138
 ├── Hypothesis
 ├── Change
 ├── Test
 ├── Result
 └── Verdict
```

#### 3. کوچک‌ترین تغییر ممکن
Patch باید:
- محدود باشد.
- قابل revert باشد.
- فقط یک فرضیه را تست کند.

#### 4. Regression Order
ترتیب تست همیشه:
1. Golden Game (Dreaming Sarah)
2. Known Working Games (Arise)
3. Regression Games
4. New Target (Yatzi)

#### 5. Dreaming Sarah Rule
- وضعیت: **CONFIRMED WORKING**
- وظیفه: بعد از هر تغییر، اجرا شود برای Regression.
- موارد بررسی: Frames, Colors, Crash, Framebuffer, Resolver

#### 6. Arise Rule
- هدف: بررسی GPU Memory Regression
- چک: GPU mapping, Memory fault, NID resolve, Framebuffer

#### 7. Yatzi Rule
- Yatzi فقط بعد از PASS شدن Dreaming Sarah و Arise.
- بررسی: Resolver, IL2CPP, Semaphore, Rendering Pipeline

#### 8. Build Requirement
قبل از Runtime:
```bash
dotnet build -c Release
```
اگر Build نشد: نباید Runtime نتیجه‌گیری شود.

#### 9. Sandbox Limitation Reporting
اگر محیط محدود است (مثلا dotnet SDK missing, No GPU, No Vulkan device):
- باید واضح نوشته شود.

#### 10. Static Verification ≠ Runtime Validation
- Static: Code looks correct
- Runtime: Actual execution works

این دو جدا گزارش شوند.

---

## EXP-138 Current Investigation State

### Patch Applied

```
Commit: 9cef960
Title:  EXP-138: Apply TryCallGuestFunction RAX propagation fix
```

### Root Cause Found

**مشکل:** Guest callback return value lost

**قبل:**
```
Host RAX
 ↓
lost
 ↓
context.Rax = 0
 ↓
Resolver returns NULL
 ↓
IL2CPP fails
 ↓
Unity Job System deadlock
```

**بعد:**
```
nativeReturn
 ↓
context.Rax
 ↓
Guest receives real value
```

### EXP-138 Changes

#### DirectExecutionBackend.cs

| Change | What | Goal |
|--------|------|------|
| 1 | `CallNativeEntry`: `int` → `ulong` | حفظ pointer های 64-bit |
| 2 | `ExecuteGuestThreadEntry`: added `context.Rax = nativeReturn` | Write-back host RAX |
| 3 | `ExecuteGuestContinuationEntry`: added `context.Rax = nativeReturn` | Same write-back for continuation |
| 4 | `num6`: `int` → `ulong` | جلوگیری از pointer truncation |
| 5 | Format: `X8` → `X16` | نمایش کامل address |

#### NativeWorker.cs

| Change | What | Goal |
|--------|------|------|
| 6 | `RunGuestEntryStub`: `int` → `ulong` | consistency |

### Validation Status

#### Static Verification

**وضعیت:** ✅ PASS

| مورد | نتیجه |
|------|-------|
| CallNativeEntry ulong | PASS |
| Delegate signature | PASS |
| RAX propagation | PASS |
| Thread entry update | PASS |
| Continuation entry update | PASS |
| Pointer width | PASS |
| grep validation | PASS |

#### Runtime Validation

**وضعیت:** ❌ BLOCKED

**دلیل:** No dotnet SDK

**مشکل:**
```
dotnet: command not found
```

---

## Required Maintainer Test

### Step 1 — Build

```bash
git pull origin main
dotnet build -c Release
```

### Step 2 — Dreaming Sarah Golden Test (اجباری)

```bash
SHARPEMU_HEADLESS=1 \
SHARPEMU_CAPTURE=1 \
./SharpEmu.CLI --game dreaming-sarah --timeout 30
```

**PASS:**
- Frames >= 138
- Colors >= 167
- Crash = 0

### Step 3 — Arise Regression

```bash
./SharpEmu.CLI --game arise --timeout 30
```

**بررسی:**
- No GPU memory fault
- No new unresolved NID
- Framebuffer valid

### Step 4 — Yatzi (فقط بعد از PASS قبلی)

```bash
SHARPEMU_SEMA_FAST_PATH=0 \
./SharpEmu.CLI --game yatzi --timeout 60
```

**جمع‌آوری:**
```bash
grep "RESOLVER-TRACE" yatzi-exp138.log
grep "RAX=0x0000000000000000" yatzi-exp138.log | wc -l
grep "sema.signal handle=0x81" yatzi-exp138.log
grep "sema.signal handle=0x84" yatzi-exp138.log
```

**انتظار:**
- قبل: NULL resolver = 232
- بعد: NULL resolver = 0

---

## Commit Documentation

```
Commit: 36a91fa
Title:  docs: Add Agent Core Rules + Universal Debug SOP + .agent_state
```

**فایل‌ها:**
- `docs/AGENT_CORE_RULES.md`
- `docs/SOP/SHARPEMU_DEBUG_PROTOCOL.md`
- `.agent_state/current_state.md`
- `.agent_state/known_facts.md`
- `.agent_state/closed_paths.md`
- `.agent_state/experiment_history.json`
- `.agent_state/next_actions.md`

---

## وضعیت کلی پروژه

### درصد پیشرفت تخمینی

| بخش | وضعیت |
|------|-------|
| Root Cause Investigation | 90% |
| Diagnostics Infrastructure | 70% |
| Documentation | 100% |
| EXP-138 Patch | 100% |
| Runtime Validation | 0% (Blocked) |
| Yatzi Resolution | Pending |

### مرحله بعدی واقعی

دیگر نباید برگردیم به EXP-0 تا EXP-135.

**مرحله بعد:**
```
EXP-138 Runtime Validation
        ↓
Dreaming Sarah
        ↓
Arise
        ↓
Yatzi
        ↓
EXP-139 if required
```

---

## 6-Rule Quick Reference (always in agent prompt)

1. **Golden Test First** — Dreaming Sarah = CONFIRMED, not "70-80% probable".
2. **GitHub Commit Required** — no work is done until pushed + URL provided.
3. **Runtime Test Over Static Guess** — PASS / FAIL / BLOCKED, never "probably".
4. **Suspicious Issue = Immediate Test** — observe → hypothesize → test → decide.
5. **Existing Diagnostics First** — new debug code is last option.
6. **No Re-investigation of Closed Paths** — read `.agent_state/closed_paths.md` first.

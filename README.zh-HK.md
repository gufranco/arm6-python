# ARM6

以 Python 實現的 ARM60 處理器，每次推進一條指令或一個總線週期。每條指令及其花費的每個週期均以 GEC Plessey ARM60 數據手冊為準，每條指令執行後的處理器狀態則以經過濾的 ARM7TDMI 案例集為準。

[English](README.md) | [日本語](README.ja.md) | [简体中文](README.zh-Hans.md) | 繁體中文（香港）

[![CI](https://github.com/gufranco/arm6-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/arm6-python/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gufranco/arm6-python)](https://github.com/gufranco/arm6-python/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

比對 **424,220** 個錄製案例，**0** 處不一致，**62** 句引文定位到所引用的頁面，**1** 個型號，**1,087** 個測試，**100%** 語句及分支覆蓋率，無任何依賴

```python
from arm6 import Cpu, Memory

cpu = Cpu("arm60", Memory(image=(0xE3A0002A).to_bytes(4, "little"), fill=0)).reset()

spent = cpu.step()

print(f"{cpu.registers.read(0):#010x} in {spent} cycle, {cpu.spent}")
```

```
0x0000002a in 1 cycle, Cycles(s=1, n=0, i=0, c=0)
```

映像檔只有一個字，即 `mov R0, #42`。`reset()` 把程式計數器指向地址零，`step()` 執行該條指令。它花費一個順序週期，與 Table 20 給出的數據操作花費一致。`spent` 保存按數據手冊四種週期類型拆分的花費：S、N、I 和 C。

## 安裝

| 要求 | 版本 |
|:--|:--|
| Python | 3.12 或以上 |
| git | 任何版本 |
| `pdftoppm` 和 `tesseract` | 任何版本，且僅 `python3 -m conformance.quotes` 需要 |

```bash
git clone https://github.com/gufranco/arm6-python.git
cd arm6-python
python3 arm6/doctor.py
```

本套件只匯入標準庫。`pip install git+https://github.com/gufranco/arm6-python.git` 無需工作副本即可安裝，並加入一個 `arm6-doctor` 命令，執行同一個診斷腳本。

診斷腳本會檢查機器和工作副本，建立一個型號並單步執行，最後輸出一行結果。所有檢查通過時以 0 退出，否則以 1 退出。提交錯誤報告時請貼上其完整輸出。

```
  5 checks, nothing to report
```

在沒有 `pdftoppm` 或 `tesseract` 的機器上，最後一行為 `1 of 5 checks did not pass`。除引文檢查器外，其餘功能在該機器上仍可正常運作。

版本發佈遵循 [Semantic Versioning](https://semver.org/)，由 semantic-release 根據提交歷史產生。每個版本均有標籤，並列於[版本發佈頁面](https://github.com/gufranco/arm6-python/releases)。

## 介面

`arm6.Cpu(model, memory=None, seed=UNSET_SEED, fill=None, bigend=False, lateabt=True)` 建立一個型號。

| 參數 | 含義 |
|:--|:--|
| `model` | 必填。`arm60` 或其別名 `arm6`，不分大小寫。沒有預設值 |
| `memory` | 任何具有 `read_byte`、`write_byte`、`read_word` 和 `write_word` 的物件。省略時，型號會根據 `seed`、`fill` 和 `bigend` 自行建立一個 `Memory` |
| `seed` | 設定暫存器及型號自行建立的記憶體的上電內容 |
| `fill` | 改為讓每個暫存器和每個未寫入的位元組以此值開始。`fill=0` 提供一個乾淨的開始 |
| `bigend` | `bigend` 針腳。傳給型號自行建立的記憶體，提供 `memory` 時則忽略 |
| `lateabt` | `lateabt` 針腳，保存在型號上。中止針腳不會被驅動，因此它不改變任何行為 |

### 呼叫

| 呼叫 | 效果 | 返回值 |
|:--|:--|:--|
| `reset(low_cycles=2)` | Section 6.3.6：監督模式，兩個中斷禁止位均設定，從地址零取指。將重設線保持 `low_cycles` 次虛擬取指，最少 2 次，然後在異常進入上花費 3 個週期，因此預設花費 5 個週期 | 該型號 |
| `step()` | 一條指令，或進入一個待處理的 FIQ 或 IRQ | 所花費的週期數，類型為 `int` |
| `run_for(cycles)` | 執行完整指令，直至至少花費 `cycles` 個週期。指令不會被分割，因此可能超出 | 所花費的週期數 |
| `run_until(check, limit=None)` | 在 `check(cpu)` 為假時持續單步執行。經過 `limit` 條指令後拋出 `RunLimit` | 該型號 |
| `held()` | 型號是否已停止推進。沒有任何因素會令此型號停止 | `False` |
| `irq(level=True)`、`fiq(level=True)` | 設定該線。當其禁止位清除時，下一次 `step()` 會響應它 | 此刻是否會被響應 |

### 狀態

| 屬性 | 含義 |
|:--|:--|
| `model` | `Model` 記錄：`name`、`aliases`、`summary` |
| `memory` | 記憶體物件 |
| `registers` | `Registers`：`read(index)`、`write(index, value)`、`pc`、`cpsr`、`saved()`、`save(value)`、`mode` |
| `mode` | 當前的 `Mode`，從 CPSR 讀取 |
| `cycles` | 自型號建立以來的週期數，包括重設 |
| `steps` | 自上次重設以來的指令數 |
| `spent` | 上一條指令的花費，類型為 `Cycles` |
| `tally` | 累計總數，類型為 `Cycles`，跨重設保留 |
| `bus.cycles` | 上一條指令每個總線週期對應一個 `Cycle`：`kind`、`address`、`nopc`、`nbw`、`nrw`、`ntrans`、`lock`、`data`。`kind` 是未接協處理器的型號所驅動的表 3 週期類型之一：N、S 或 I，帶有 `letter`、`name`、`nmreq`、`seq` 及 `touches_memory` |
| `irq_line`、`fiq_line` | 每條中斷線的電平 |
| `on_cycle` | 每個總線週期後以型號為參數執行的可調用物件，或 `None`。由 `Clock` 設定 |
| `seed`、`bigend`、`lateabt` | 建構函數的參數 |

```python
from arm6 import Cpu, Memory, RunLimit

words = (0xE3A00000, 0xE2800001, 0xE3500003, 0x1AFFFFFC, 0xEAFFFFFE)
image = b"".join(word.to_bytes(4, "little") for word in words)
cpu = Cpu("arm60", Memory(image=image, fill=0), fill=0).reset()

cpu.run_until(lambda part: part.registers.pc == 0x10, limit=100)
print(cpu.registers.read(0), cpu.steps, cpu.cycles, cpu.tally)

print(cpu.run_for(10), cpu.spent, [row.kind.letter for row in cpu.bus.cycles])

try:
    cpu.run_until(lambda part: part.registers.read(0) == 4, limit=50)
except RunLimit as stopped:
    print(stopped)

print(cpu.held(), cpu.irq(), cpu.fiq(False))
```

```
3 10 19 Cycles(s=16, n=3, i=0, c=0)
12 Cycles(s=2, n=1, i=0, c=0) ['N', 'S', 'S']
gave up after 50 instructions without the predicate holding
False False False
```

該程式把 R0 計數至 3，然後跳轉到自身。十條指令花費 14 個週期，加上重設的 5 個共 19 個。`run_for(10)` 執行四次 3 週期的跳轉，報告 12。每次跳轉驅動一次非順序取指和兩次順序取指。`irq()` 返回 `False`，因為重設後 I 位處於設定狀態。

### 記憶體、暫存器和模式

`arm6.Memory(image=None, seed=UNSET_SEED, fill=None, bigend=False)` 是 4 GB 的稀疏記憶體。`image` 從地址零開始寫入。任何未被寫入的位元組讀出 `fill`，若 `fill` 為 `None`，則讀出由 `seed` 和地址推導出的值。可用的呼叫為 `read_byte`、`write_byte`、`read_word` 和 `write_word`。字存取忽略地址的兩個低位。`written` 把每個已寫入的地址映射到其位元組。

`arm6.Registers` 保存 31 個通用暫存器和 6 個狀態暫存器。`read(15)` 返回清除兩個低位後的程式計數器。

```python
from arm6 import MODES, UNSET_SEED, VECTORS, Cpu, Memory

little = Memory(image=b"\x78\x56\x34\x12", fill=0)
big = Memory(image=b"\x78\x56\x34\x12", fill=0, bigend=True)
print(f"{little.read_word(0):#010x} {big.read_word(0):#010x} {little.read_byte(3):#04x}")

little.write_word(0x2002, 0xCAFEF00D)
print(f"{little.read_word(0x2000):#010x}", [hex(one) for one in sorted(little.written)[-4:]])
print(Memory(seed=1).read_byte(0x100) != Memory(seed=2).read_byte(0x100), hex(UNSET_SEED))

cpu = Cpu("arm60", fill=0).reset()
print(f"{cpu.registers.cpsr:#010x}", cpu.mode.name, cpu.mode.privileged)
print(cpu.registers.general_count(), cpu.registers.status_count())

print(VECTORS["irq"], VECTORS["fiq"])
print([name for name, mode in MODES.items() if not mode.wide])
```

```
0x12345678 0x78563412 0x12
0xcafef00d ['0x2000', '0x2001', '0x2002', '0x2003']
True 0x5a5a5a5a
0x000000d3 svc32 True
31 6
24 28
['usr26', 'fiq26', 'irq26', 'svc26']
```

設定 `bigend` 後，同樣四個位元組讀出兩個不同的字。在 0x2002 寫入的字落在 0x2000。兩個種子給出兩個不同的上電位元組。重設後 CPSR 為 `0xd3`：監督模式，I 位和 F 位均設定。

| 名稱 | 內容 |
|:--|:--|
| `arm6.MODES` | 十個 `Mode` 記錄，以名稱為鍵：`usr32`、`fiq32`、`irq32`、`svc32`、`abt32`、`und32`，以及 26 位的 `usr26`、`fiq26`、`irq26`、`svc26`。每個記錄有 `bits`、`wide`、`privileged`、`bank` 和 `spsr` |
| `arm6.VECTORS` | 按名稱列出的七個異常向量，由位於 0x00 的 `reset` 至位於 0x1C 的 `fiq` |
| `arm6.UNSET_SEED` | 未提供種子時使用的種子 |

### 目錄和錯誤

| 名稱 | 內容 |
|:--|:--|
| `arm6.MODELS` | 唯一的 `Model` 記錄，以 `arm60` 為鍵 |
| `arm6.Model` | 一個目錄項目。它拒絕所有屬性寫入 |
| `arm6.Arm6Error` | 以下所有錯誤的基類 |
| `arm6.UnknownModelError` | 當名稱不屬於任何型號或為空時，由 `Cpu` 拋出。訊息會列出所有接受的名稱 |
| `arm6.RunLimit` | 經過 `limit` 條指令而 `check` 仍未成立時，由 `run_until` 拋出 |
| `arm6.EmptyRegisterList` | 遇到未列出任何暫存器的區塊傳輸時，由 `step` 拋出。Section 7.9 禁止這種情況，但沒有說明型號會如何處理 |
| `arm6.UnspecifiedEncoding` | 遇到不匹配 Figure 28 任何一行的字時，由 `step` 拋出 |
| `arm6.NoCoprocessor` | 已公開但從不拋出。協處理器指令會進入未定義指令陷阱，與 section 10.15 所述未連接協處理器時的行為一致 |
| `arm6.UnknownMode` | 當 CPSR 模式欄位不屬於十種模式中的任何一種時拋出 |
| `arm6.WaitsRequired` | 由 `Cycles.ticks(None)` 拋出 |
| `arm6.BadWaits` | 數值小於 1 時由 `Waits` 拋出 |
| `arm6.ClockClosed` | 在 `close()` 之後由 `Clock.tick()` 拋出 |
| `arm6.Truncated` | 當偏移處剩餘不足四個位元組時，由解碼器拋出。`offset` 保存其位置。`disassemble` 會在該處結束列表，而不是拋出 |
| `arm6.__version__` | 已安裝的版本 |

```python
from arm6 import MODELS, Cpu, EmptyRegisterList, Memory, UnknownModelError, UnspecifiedEncoding

for name, model in MODELS.items():
    print(name, model.aliases, Cpu("arm6"), Cpu("ARM60").model.name)

for wrong in ("arm610", ""):
    try:
        Cpu(wrong)
    except UnknownModelError as refused:
        print(str(refused).split(".")[0])


def first_word(word):
    return Cpu("arm60", Memory(image=word.to_bytes(4, "little"), fill=0), fill=0).reset()


for word in (0xE8BD0000, 0xE00000F0):
    try:
        first_word(word).step()
    except (EmptyRegisterList, UnspecifiedEncoding) as refused:
        print(type(refused).__name__, hex(word))

part = first_word(0xEE000000)
part.step()
print(part.mode.name, part.registers.pc)
```

```
arm60 ('arm6',) Cpu('arm60') arm60
'arm610' is not a model this package covers: arm6, arm60
name a model: arm6, arm60
EmptyRegisterList 0xe8bd0000
UnspecifiedEncoding 0xe00000f0
und32 4
```

名稱匹配不分大小寫。列表為空的區塊傳輸，以及 Figure 28 中沒有對應行的字，都會被拒絕，而不是靠猜測處理。協處理器指令會在地址 4 的向量處進入未定義模式。

## 以真實速度執行

`step` 報告週期數，但不說明它們花了多長時間：

```python
from arm6 import Cpu, Waits

cpu = Cpu("arm60", fill=0).reset()
cpu.step()

print(cpu.spent.ticks(Waits(sequential=1, nonsequential=3, internal=1, coprocessor=1)))
```

```
1
```

Section 8.6 指出 `mclk` 可以無限延長，也可以改用 `Nwait` 插入完整週期。針腳表補充指出，在不需要等待的系統中，`Nwait` 可接到 HIGH。因此一個週期需時多久，取決於電路板。`Waits` 描述一塊電路板：每種週期類型花費的 `mclk` 週期數，每個至少為 1。`Cycles.ticks(waits)` 把四個計數分別乘以這些數值。在沒有電路板的情況下請求節拍數會被拒絕：

```python
from arm6 import Cpu, WaitsRequired

cpu = Cpu("arm60", fill=0).reset()
cpu.step()

try:
    cpu.spent.ticks(None)
except WaitsRequired as refused:
    print(str(refused)[:53])
```

```
ARM60 puts memory timing on the Nwait pin and section
```

`Cycles` 有 `s`、`n`、`i`、`c` 和 `total`，可與另一個 `Cycles` 相加，並拒絕所有屬性寫入。在針腳表明確指出的唯一配置下，即 `Nwait` 接到 HIGH、每個週期一個 `mclk`，`total` 也就是節拍數。

## 逐週期驅動

`step` 執行一整條指令。`arm6.Clock(cpu)` 在一個線程上執行型號，並在每個總線週期處將其阻塞，因此調用者可以在同一條指令的兩個週期之間停下：

```python
from arm6 import Clock, Cpu, Memory

image = (0xEB000000).to_bytes(4, "little") + (0xE1A00001).to_bytes(4, "little") * 8
cpu = Cpu("arm60", Memory(image=image, fill=0), fill=0).reset()

with Clock(cpu) as clock:
    clock.run_for(2)
    print(clock.cycles, cpu.registers.pc, len(cpu.bus.cycles))
```

```
2 8 2
```

第一個字是跳轉到地址 8 的帶連結跳轉，花費 3 個週期。經過 2 個週期後，計數器已指向目標，而第三個週期，即第二次重新填充取指，尚未發生。`Cpu.run_for` 無法停在這裏，因為它以完整指令為單位花費週期。

| Clock 呼叫 | 效果 | 返回值 |
|:--|:--|:--|
| `tick()` | 讓型號執行一個總線週期。在 `close()` 之後拋出 `ClockClosed`，並重新拋出型號拋出的任何異常 | 週期計數 |
| `run_for(cycles)` | `cycles` 次節拍 | 週期計數 |
| `close()` | 停止線程並恢復型號的 `on_cycle`。`with` 區塊會呼叫它 | `None` |
| 迭代 | 每一步是一次 `tick()`，直至時鐘關閉 | 週期計數 |
| `cycles`、`closed`、`cpu` | 目前為止的節拍數、是否已關閉、它所驅動的型號 | |

```python
from arm6 import Clock, ClockClosed, Cpu

cpu = Cpu("arm60", fill=0).reset()
clock = Clock(cpu)

for count in clock:
    if count == 3:
        break

print(clock.tick(), cpu.steps, clock.closed)
clock.close()

try:
    clock.tick()
except ClockClosed as refused:
    print(refused, cpu.on_cycle)
```

```
4 3 False
this clock has been closed None
```

使用 `fill=0` 時，每個字都是 1 週期的 `andeq`。四次節拍完成三條指令，並把第四條保持在其唯一的週期之內。

## 型號

```python
from arm6 import MODELS, Cpu

print(sorted(MODELS))
print(Cpu("arm60").model.name, Cpu("arm6").model.name, Cpu("ARM60").model.name)
```

```
['arm60']
arm60 arm60 arm60
```

`arm60` 是名稱，`arm6` 是其別名。目錄只有一個項目，但仍會拒絕不屬於任何型號的名稱，並列出所有接受的名稱。

ARM60、ARM600 和 ARM610 的核心相同。ARM610 數據手冊指出 ARM610 內的 CPU 是 ARM6，並把與 ARM600 的差異列為五項總線及封裝上的不同。總線有所不同，而本套件把有時鐘的晶片建模至總線層面。只有 ARM60 有文件逐週期給出其總線行為，因此這裏只有 ARM60。ARM600、ARM610 和 ARM61 列於 [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md)，並說明每份缺失的文件能解決甚麼問題。

## 只讀不執行

`arm6.disassemble(data, offset=0, address=0, count=None, stop_at_return=False)` 讀取字而不執行它們。以下是一個等待狀態位然後讀取一個位元組的例程：

```python
from arm6 import disassemble

words = (0xE92D4010, 0xE3A04101, 0xE5D40020, 0xE3100001, 0x0AFFFFFC, 0xE5D40000, 0xE8BD8010)
image = b"".join(word.to_bytes(4, "little") for word in words)

for one in disassemble(image, address=0x100, stop_at_return=True):
    print(f"0x{one.address:06X}  {one.word:08X}  {one.text}")
```

```
0x000100  E92D4010  stmdb SP!, {R4, LR}
0x000104  E3A04101  mov R4, #0x40000000
0x000108  E5D40020  ldrb R0, [R4, #0x20]
0x00010C  E3100001  tst R0, #0x1
0x000110  0AFFFFFC  beq 0x000108
0x000114  E5D40000  ldrb R0, [R4]
0x000118  E8BD8010  ldmia SP!, {R4, PC}
```

每個結果都是一個 `arm6.Instruction`，具有 `address`、`offset`、`word`、`condition`、`mnemonic`、`kind`、`operand`、`size` 和 `text`。`condition` 和 `kind` 使用數據手冊中的名稱。`operand` 是運算元欄位所表示的那一個數字，在定址方式自足時會解析為地址：

```python
from arm6 import disassemble

image = bytes.fromhex("04 10 9f e5 0e f0 a0 e1 78 56 34 12")

for one in disassemble(image, address=0x8000, count=2):
    print(one.text, "|", one.kind, one.condition, one.mnemonic, one.operand)

print(len(disassemble(b"\x00\x00\xa0\xe1\x00")))
```

```
ldr R1, [PC, #0x4] | single data transfer AL ldr 32780
mov PC, LR | data processing AL mov None
1
```

相對於程式計數器的載入會報告其字面值所在的地址 0x800C，輸出為 32780。`mov` 不帶任何數字，因此其 `operand` 為 `None`。`count` 在讀取該數量的字後停止。結尾不足一個字的片段會結束列表。

`disassemble` 依次讀取，不跟隨任何跳轉，因為一個字是否為程式碼取決於控制流如何到達它。此型號沒有返回指令，只有一個任何指令都可寫入的程式計數器。`stop_at_return` 只在編譯器為返回生成的兩種形式之後停止，即 `mov PC, LR` 和載入 PC 的 `ldm`，其他情況一律不停。

十一種類型就是 Figure 28 的各行。該圖沒有跳轉並交換行、半字傳輸行、有號載入行和長乘法行。不匹配任何一行的字會報告為 `unspecified`，而不是靠猜測處理。

## 沒有乾淨的開始

```python
from arm6 import Cpu

cpu = Cpu("arm60", seed=7)

print(cpu.registers.read(0) != 0, cpu.registers.pc != 0)
```

```
True True
```

建構時，每個暫存器，包括程式計數器，都會處於由 `seed` 推導出的狀態。在重設之前單步執行的型號會從該地址開始執行，與晶片上電後的情況相同。

`reset()` 是調用者取得已知狀態的方法，以上每個例子都以它開始。它只寫入 section 6.3.6 所列的內容：監督模式、兩個中斷禁止位，以及從地址零取指。它寫入的已保存計數器和狀態是打亂的，因為數據手冊指出其值未定義。它花費數據手冊要求的兩個週期虛擬取指，加上異常進入的三個週期，這五個週期會計入 `cycles` 和 `tally`：

```python
from arm6 import Cpu

cpu = Cpu("arm60", fill=0).reset()

print(cpu.registers.pc, cpu.mode.name, cpu.cycles, cpu.steps)
```

```
0 svc32 5 0
```

計數器位於重設向量，時鐘已經前進，而指令計數沒有。本儲存庫中只有一處改為手動設定計數器：案例集執行器，因為錄製的案例會聲明計數器、模式和中斷禁止位，而重設會破壞要比對的狀態。

## 它是否正確

三項檢查約束着它，沒有一項是拿本套件與自身比較。

**數據手冊，經引用並核對。** [`conformance/hardware.json`](conformance/hardware.json) 中的每項事實都附有其出處的句子及頁碼。`python3 -m conformance.quotes` 把全部 **62** 句定位到所引用的頁面。ARM60 數據手冊沒有文字層：`pdftotext` 對其八十三頁只返回八十三個字元。因此 [`conformance/quotes.py`](conformance/quotes.py) 用 `pdftoppm` 渲染每個被引用的頁面，用 `tesseract` 讀取，並按引文中有多少個五詞窗口出現在該頁來評分。

**經過濾的案例集，只比對狀態。** `python3 -m conformance.singlestep` 執行來自 `SingleStepTests/ARM7TDMI` 的 **424,220** 個錄製案例，該案例集按提交固定版本，並在每個案例後比對完整的處理器狀態。不一致之處為 **0**。該案例集錄製自較後期的晶片，因此其 1,000,000 個 ARM 狀態案例中有 575,780 個被過濾掉。[`conformance/suites.json`](conformance/suites.json) 中的每項排除都列明其依據的句子。不讀取任何週期、存取或交易次序欄位：ARM60 乘法的最壞情況為 `1S+16I`，ARM7TDMI 的為 `1S+4I`，因此該晶片的交易流描述的是另一種總線。

**週期表。** 每種指令形式的花費都由各模組旁的測試對照 Table 20 檢查。除了總數，總線記錄也會比對，因為一個模型可能花費正確的週期數，卻驅動錯誤的地址。

尚未確定的問題列於 [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md)，各文件之間的分歧列於 [`conformance/divergences.json`](conformance/divergences.json)。第一個未解問題是凌駕於這一切之上的上限：這裏沒有任何內容建基於對真實晶片的測量。

| 命令 | 參數 | 退出碼 |
|:--|:--|:--|
| `python3 arm6/doctor.py` | 無 | 所有檢查通過時為 0，否則為 1 |
| `python3 -m conformance.quotes` | 無 | 所有可讀取的引文均已定位時為 0，否則為 1。機器上沒有文件時，它不檢查任何內容並如實說明 |
| `python3 -m conformance.singlestep [path]` | 案例集的 `v1` 目錄，預設為 `ARM7TDMI/v1`。`--limit N` 限制每個檔案的案例數，`--count` 只計數不比對，`--files` 輸出需要取得的路徑 | 沒有不一致或沒有案例集時為 0，有任何不一致時為 1 |
| `python3 -m conformance.speed` | `--cycles N`，預設 200,000，以及 `--repeats N`，預設 7 | 高於下限時為 0，低於下限時為 1，選項錯誤時為 2 |
| `python3 -m conformance.documents` | `--check` 只驗證不下載，`--only SUBSTRING` 選擇文件 | 所有文件驗證通過時為 0，否則為 1 |
| `python3 -m conformance.links` | 無。它會探測本 README 中的每個地址 | 0，除非有地址返回 404 或 410 |
| `python3 -m conformance.package <wheel>` | 一個已建置的 wheel | 所有模組均已包含且不含任何測試時為 0，否則為 1，沒有參數時為 2 |

## 參與開發

| 需要 | 位置 |
|:--|:--|
| 所有關卡檢查及其執行次序 | [CONTRIBUTING.md](CONTRIBUTING.md) |
| 供編程代理使用的相同內容 | [AGENTS.md](AGENTS.md) |
| 本儲存庫與同系列其他儲存庫共用的標準 | [FAMILY.md](FAMILY.md) |
| 錯誤報告 | [GitHub Issues](https://github.com/gufranco/arm6-python/issues) |
| 安全報告 | [SECURITY.md](SECURITY.md) |

```bash
uvx ruff@0.16.3 format --check .
uvx ruff@0.16.3 check .
uvx mypy@1.14.1
python3 arm6/core.test.py
```

每個模組旁都有一個以其命名的測試檔案，每個都可如上所示獨立執行。覆蓋率是一道硬性關卡檢查，要求語句和分支達到 100%。`python3 -m conformance.speed` 是吞吐量下限，在覆蓋率步驟之外執行，因為覆蓋率追蹤器的開銷約為模型本身的十倍。

## 參考資料

這些文件均不可轉載，也不在本儲存庫中。個別句子連同其所在頁碼引用於 [`conformance/hardware.json`](conformance/hardware.json)。每一行列出頁數及檔案 SHA-256 的前十六個十六進位數字。

| 文件 | 日期 | 頁數 | SHA-256 |
|:--|:--|--:|:--|
| [GEC Plessey Semiconductors, *ARM60 Datasheet*, Issue 0.81](https://3dodev.com/_media/documentation/hardware/arm60_datasheet_-_gec_plessey_semiconductors.pdf) | 1993 | 83 | `315dbff7b6259a73` |
| [Advanced RISC Machines, *ARM610 Data Sheet*, ARM DDI 0004D](https://bitsavers.org/pdf/acorn/ARM_DDI_0004D_ARM610_Data_Sheet_Aug93.pdf) | 1993-08 | 134 | `76f13ffe2bc20774` |
| [Advanced RISC Machines, *Application Note 11: Differences Between ARM6 and Earlier ARM Processors*](https://home.marutan.net/rpcemu/Apps11vC.html) | 未註明日期 | 1 | `41239bc21c8e3375` |

[`conformance/documents.json`](conformance/documents.json) 記錄每份文件的完整摘要值、位元組數及可下載的地址。`python3 -m conformance.documents` 把三份文件全部下載到 git 忽略的 `docs/`，並拒絕任何摘要值不符的檔案。`--check` 驗證已存在的副本。由於上面連結的地址對普通請求返回 403，清單改從鏡像站取得 ARM610 數據手冊。兩者提供相同的位元組。

以 ARM60 數據手冊為準。它是找到的唯一一份按指令、按週期給出此晶片總線行為的文件。ARM610 數據手冊是指令集和程式員模型的第二個佐證，僅此而已：其總線章節描述兩個時鐘、兩種週期類型和一個快取。Application Note 11 是找到的唯一一份列出四種 26 位模式編碼的文件，而兩份數據手冊都沒有列出。

[SingleStepTests/ARM7TDMI](https://github.com/SingleStepTests/ARM7TDMI) 提供錄製的案例。其提交及每項過濾條目均列於 [`conformance/suites.json`](conformance/suites.json)。

## 引用本專案

[CITATION.cff](CITATION.cff) 會在每次發佈時，由標記套件版本的腳本更新。

## 授權

MIT。請參閱 [LICENSE](LICENSE)。

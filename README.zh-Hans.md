# ARM6

用 Python 实现的 ARM60 处理器，每次推进一条指令或一个总线周期。每条指令及其耗费的每个周期都以 GEC Plessey ARM60 数据手册为准，每条指令执行后的处理器状态则以经过筛选的 ARM7TDMI 语料库为准。

[English](README.md) | [日本語](README.ja.md) | 简体中文 | [繁體中文（香港）](README.zh-HK.md)

[![CI](https://github.com/gufranco/arm6-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/arm6-python/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gufranco/arm6-python)](https://github.com/gufranco/arm6-python/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

已比对 **424,220** 个录制用例，**0** 处不一致，**62** 句引文已定位到所引用的页面，**1** 个器件，**1,181** 个测试，**100%** 语句与分支覆盖率，无依赖

```python
from arm6 import Cpu, Memory

cpu = Cpu("arm60", Memory(image=(0xE3A0002A).to_bytes(4, "little"), fill=0)).reset()

spent = cpu.step()

print(f"{cpu.registers.read(0):#010x} in {spent} cycle, {cpu.spent}")
```

```
0x0000002a in 1 cycle, Cycles(s=1, n=0, i=0, c=0)
```

该镜像只有一个字，即 `mov R0, #42`。`reset()` 将程序计数器指向地址零，`step()` 执行这一条指令。它耗费一个顺序周期，与 Table 20 对数据操作给出的值一致。`spent` 保存按数据手册四种周期类型拆分的开销：S、N、I 和 C。

## 安装

| 要求                      | 版本                                           |
| :------------------------ | :--------------------------------------------- |
| Python                    | 3.12 或更高                                    |
| git                       | 任意                                           |
| `pdftoppm` 和 `tesseract` | 任意，且仅用于 `python3 -m conformance.quotes` |

```bash
git clone https://github.com/gufranco/arm6-python.git
cd arm6-python
python3 arm6/doctor.py
```

该包只导入标准库中的内容。`pip install git+https://github.com/gufranco/arm6-python.git` 无需检出即可安装它，并添加一个 `arm6-doctor` 命令，运行同一个诊断脚本。

诊断脚本检查机器和检出目录，构建一个器件并单步执行，最后输出一行。所有检查都通过时退出码为 0，否则为 1。提交缺陷报告时请粘贴它的完整输出。

```
  5 checks, nothing to report
```

在没有 `pdftoppm` 或 `tesseract` 的机器上，最后一行为 `1 of 5 checks did not pass`。在那里，除引文检查器外的一切仍然可用。

版本发布遵循[语义化版本](https://semver.org/)，由 semantic-release 根据提交历史生成。每个版本都打了标签，并列在[发布页面](https://github.com/gufranco/arm6-python/releases)上。

## 接口

`arm6.Cpu(model, memory=None, seed=UNSET_SEED, fill=None, bigend=False, lateabt=True)` 构建一个器件。

| 参数      | 含义                                                                                                                                  |
| :-------- | :------------------------------------------------------------------------------------------------------------------------------------ |
| `model`   | 必填。`arm60` 或其别名 `arm6`，大小写不限。没有默认值                                                                                 |
| `memory`  | 任何具有 `read_byte`、`write_byte`、`read_word` 和 `write_word` 的对象。省略时，器件根据 `seed`、`fill` 和 `bigend` 构建一个 `Memory` |
| `seed`    | 设定寄存器以及器件所构建内存的上电内容                                                                                                |
| `fill`    | 改为让每个寄存器和每个未写入的字节都从这个值开始。`fill=0` 给出一个无噪声的起始状态                                                   |
| `bigend`  | `bigend` 引脚。传给器件所构建的内存，提供 `memory` 时忽略                                                                             |
| `lateabt` | `lateabt` 引脚，保存在器件上。中止引脚不被驱动，因此它不改变任何行为                                                                  |

### 调用

| 调用                                 | 作用                                                                                                                                                           | 返回值                       |
| :----------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------- | :--------------------------- |
| `reset(low_cycles=2)`                | Section 6.3.6：管理模式，两个中断禁止位都置位，从地址零取指。复位线保持 `low_cycles` 次空取指，不少于 2 次，随后异常进入耗费 3 个周期，因此默认开销为 5 个周期 | 该器件                       |
| `step()`                             | 执行一条指令，或进入一个待处理的 FIQ 或 IRQ                                                                                                                    | 它耗费的周期数，类型为 `int` |
| `run_for(cycles)`                    | 执行完整的指令，直到至少耗费 `cycles` 个周期。指令从不拆分，因此可能超出                                                                                       | 耗费的周期数                 |
| `run_until(check, limit=None)`       | 在 `check(cpu)` 为假时持续单步执行。执行 `limit` 条指令后抛出 `RunLimit`                                                                                       | 该器件                       |
| `held()`                             | 器件是否已停止推进。没有任何东西会让这个器件停下                                                                                                               | `False`                      |
| `irq(level=True)`, `fiq(level=True)` | 设置该线的电平。其禁止位清零时，下一次 `step()` 会响应它                                                                                                       | 现在是否会被响应             |

### 状态

| 属性                        | 含义                                                                                                                                                                                                                                    |
| :-------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `model`                     | `Model` 记录：`name`、`aliases`、`summary`                                                                                                                                                                                              |
| `memory`                    | 内存对象                                                                                                                                                                                                                                |
| `registers`                 | `Registers`：`read(index)`、`write(index, value)`、`pc`、`cpsr`、`saved()`、`save(value)`、`mode`                                                                                                                                       |
| `mode`                      | 当前的 `Mode`，从 CPSR 读取                                                                                                                                                                                                             |
| `cycles`                    | 自器件构建以来的周期数，包括复位                                                                                                                                                                                                        |
| `steps`                     | 自上次复位以来的指令数                                                                                                                                                                                                                  |
| `spent`                     | 上一条指令的开销，类型为 `Cycles`                                                                                                                                                                                                       |
| `tally`                     | 累计总数，类型为 `Cycles`，跨复位保留                                                                                                                                                                                                   |
| `bus.cycles`                | 上一条指令的每个总线周期对应一个 `Cycle`：`kind`、`address`、`nopc`、`nbw`、`nrw`、`ntrans`、`lock`、`data`。`kind` 是未接协处理器的器件所驱动的表 3 周期类型之一：N、S 或 I，带有 `letter`、`name`、`nmreq`、`seq` 和 `touches_memory` |
| `irq_line`, `fiq_line`      | 每条中断线的电平                                                                                                                                                                                                                        |
| `on_cycle`                  | 在每个总线周期结束、该周期的工作完成之后以器件为参数运行的可调用对象，或 `None`。由 `Clock` 设置                                                                                                                                        |
| `seed`, `bigend`, `lateabt` | 构造函数参数                                                                                                                                                                                                                            |

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

该程序将 R0 递增到 3，然后跳转到自身。十条指令耗费 14 个周期，加上复位的 5 个，共 19 个。`run_for(10)` 执行了四次 3 周期的跳转，报告 12。每次跳转驱动一次非顺序取指和两次顺序取指。`irq()` 返回 `False`，因为复位使 I 位保持置位。

### 内存、寄存器与模式

`arm6.Memory(image=None, seed=UNSET_SEED, fill=None, bigend=False)` 是 4 GB 的稀疏内存。`image` 从地址零开始写入。任何未被写入的字节读出为 `fill`，当 `fill` 为 `None` 时，则读出由 `seed` 和地址派生的值。可用的调用是 `read_byte`、`write_byte`、`read_word` 和 `write_word`。字访问忽略地址的低两位。`written` 将每个已写入的地址映射到其字节。

`arm6.Registers` 包含 31 个通用寄存器和 6 个状态寄存器。`read(15)` 返回低两位清零后的程序计数器。

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

设置 `bigend` 后，同样的四个字节读出为两个不同的字。写入 0x2002 的字落在 0x2000。两个种子给出两个不同的上电字节。复位后 CPSR 为 `0xd3`：管理模式，I 位和 F 位置位。

| 名称              | 内容                                                                                                                                                                                             |
| :---------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `arm6.MODES`      | 十个 `Mode` 记录，以名称为键：`usr32`、`fiq32`、`irq32`、`svc32`、`abt32`、`und32`，以及 26 位的 `usr26`、`fiq26`、`irq26`、`svc26`。每个记录都有 `bits`、`wide`、`privileged`、`bank` 和 `spsr` |
| `arm6.VECTORS`    | 七个异常向量，按名称索引，从位于 0x00 的 `reset` 到位于 0x1C 的 `fiq`                                                                                                                            |
| `arm6.UNSET_SEED` | 未给出种子时使用的种子                                                                                                                                                                           |

### 目录与错误

| 名称                       | 内容                                                                                                        |
| :------------------------- | :---------------------------------------------------------------------------------------------------------- |
| `arm6.MODELS`              | 唯一的 `Model` 记录，以 `arm60` 为键                                                                        |
| `arm6.Model`               | 一个目录条目。它拒绝任何属性写入                                                                            |
| `arm6.Arm6Error`           | 以下所有错误的基类                                                                                          |
| `arm6.UnknownModelError`   | 名称不对应任何型号或名称为空时，由 `Cpu` 抛出。消息列出所有可接受的名称                                     |
| `arm6.RunLimit`            | 经过 `limit` 条指令而 `check` 仍不成立时，由 `run_until` 抛出                                               |
| `arm6.EmptyRegisterList`   | `step` 遇到未列出任何寄存器的块传送时抛出。Section 7.9 禁止这种情况，但没有说明器件会怎样做                 |
| `arm6.UnspecifiedEncoding` | `step` 遇到与 Figure 28 任何一行都不匹配的字时抛出                                                          |
| `arm6.NoCoprocessor`       | 已公开，但从不抛出。协处理器指令会进入未定义指令陷阱，与 section 10.15 所说的未连接协处理器时的行为一致     |
| `arm6.UnknownMode`         | CPSR 的模式字段不是十种模式中的任何一种时抛出                                                               |
| `arm6.WaitsRequired`       | 由 `Cycles.ticks(None)` 抛出                                                                                |
| `arm6.BadWaits`            | `Waits` 收到小于 1 的数值时抛出                                                                             |
| `arm6.ClockClosed`         | 在 `close()` 之后调用 `Clock.tick()` 时抛出                                                                 |
| `arm6.Truncated`           | 偏移处剩余不足四个字节时，由解码器抛出。`offset` 保存出错的位置。`disassemble` 会在那里结束列表，而不是抛出 |
| `arm6.__version__`         | 已安装的版本                                                                                                |

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

名称匹配不区分大小写。寄存器列表为空的块传送，以及 Figure 28 中没有对应行的字，都会被拒绝，而不是猜测处理。协处理器指令在地址 4 的向量处进入未定义模式。

## 以真实速度运行

`step` 报告周期数，但不说明这些周期耗时多久：

```python
from arm6 import Cpu, Waits

cpu = Cpu("arm60", fill=0).reset()
cpu.step()

print(cpu.spent.ticks(Waits(sequential=1, nonsequential=3, internal=1, coprocessor=1)))
```

```
1
```

Section 8.6 说 `mclk` 可以无限拉伸，也可以改由 `Nwait` 插入整个周期。引脚表补充说，在不需要等待的系统中，`Nwait` 可以接 HIGH。因此，一个周期耗时多久是电路板层面的事实。`Waits` 描述一块电路板：每种周期类型耗费的 `mclk` 周期数，每项至少为 1。`Cycles.ticks(waits)` 将四个计数分别乘以这些数值。没有电路板就请求节拍数会被拒绝：

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

`Cycles` 具有 `s`、`n`、`i`、`c` 和 `total`，可以与另一个 `Cycles` 相加，并拒绝任何属性写入。在引脚表明确给出的唯一配置下，即 `Nwait` 接 HIGH、每个周期一个 `mclk`，`total` 同时也是节拍数。

## 逐周期驱动

`step` 执行一整条指令。`arm6.Clock(cpu)` 在一个线程上运行器件，并在每个总线周期处阻塞它，因此调用方可以在同一条指令的两个周期之间停下：

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

第一个字是跳转到地址 8 的带链接跳转，耗费 3 个周期。2 个周期之后，计数器已经指向目标地址，而第三个周期，即第二次重新填充取指，尚未发生。`Cpu.run_for` 无法停在那里，因为它以完整指令为单位耗费周期。

| Clock 调用                | 作用                                                                                      | 返回值   |
| :------------------------ | :---------------------------------------------------------------------------------------- | :------- |
| `tick()`                  | 让器件运行一个总线周期。在 `close()` 之后抛出 `ClockClosed`，并重新抛出器件抛出的任何异常 | 周期计数 |
| `run_for(cycles)`         | `cycles` 个节拍                                                                           | 周期计数 |
| `close()`                 | 停止线程，并恢复器件的 `on_cycle`。`with` 块会调用它                                      | `None`   |
| 迭代                      | 每一步是一次 `tick()`，直到时钟关闭                                                       | 周期计数 |
| `cycles`, `closed`, `cpu` | 到目前为止的节拍数、是否已关闭、它驱动的器件                                              |          |

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
4 4 False
this clock has been closed None
```

在 `fill=0` 下，每个字都是 1 周期的 `andeq`。四个节拍运行四条指令。节拍要等其周期的全部工作完成后才停下，所以无论之后是否关闭时钟，器件的状态都与调用四次 `step()` 后相同。

## 型号

```python
from arm6 import MODELS, Cpu

print(sorted(MODELS))
print(Cpu("arm60").model.name, Cpu("arm6").model.name, Cpu("ARM60").model.name)
```

```
['arm60']
arm60 arm60 arm60
```

`arm60` 是名称，`arm6` 是它的别名。目录只有一个条目，但仍会拒绝不对应任何型号的名称，并列出它接受的所有名称。

ARM60、ARM600 和 ARM610 的内核相同。ARM610 数据手册说 ARM610 中的 CPU 就是 ARM6，并将它与 ARM600 的差异列为五项总线和封装差异。总线不同，而本包将一个时钟驱动的器件一直建模到总线层面。只有 ARM60 有文档逐周期给出其总线行为，所以这里只有 ARM60。ARM600、ARM610 和 ARM61 列在 [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) 中，并说明了每份缺失的文档能解决什么问题。

## 只读不执行

`arm6.disassemble(data, offset=0, address=0, count=None, stop_at_return=False)` 读取字而不执行它们。下面是一个等待某个状态位、然后读取一个字节的例程：

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

每个结果都是一个 `arm6.Instruction`，具有 `address`、`offset`、`word`、`condition`、`mnemonic`、`kind`、`operand`、`size` 和 `text`。`condition` 和 `kind` 使用数据手册中的名称。`operand` 是操作数字段所表示的那一个数，在寻址方式自包含时解析为地址：

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

相对于程序计数器的加载报告其字面量所在的地址 0x800C，打印为 32780。`mov` 不带数值，因此它的 `operand` 为 `None`。`count` 在读取指定数量的字之后停止。不足一个字的尾部片段会结束列表。

`disassemble` 顺序读取，不跟随任何跳转，因为一个字是否为代码取决于控制流如何到达它。这个器件没有返回指令，只有一个任何指令都可以写入的程序计数器。`stop_at_return` 在编译器为返回生成的两种形式之后停止，即 `mov PC, LR` 和加载 PC 的 `ldm`，除此之外不会在别处停止。

这十一种类型就是 Figure 28 的各行。该图没有分支并交换行、半字传送行、有符号加载行和长乘法行。不匹配任何一行的字被报告为 `unspecified`，而不是猜测处理。

## 没有任何东西以干净状态启动

```python
from arm6 import Cpu

cpu = Cpu("arm60", seed=7)

print(cpu.registers.read(0) != 0, cpu.registers.pc != 0)
```

```
True True
```

构造时，每个寄存器，包括程序计数器，都处于由 `seed` 派生的状态。在复位之前就单步执行的器件会从那个地址开始执行，就像硅片上电之后那样。

`reset()` 是调用方获得已知状态的方式，上面每个示例都以它开头。它只写入 section 6.3.6 列出的内容：管理模式、两个中断禁止位，以及从地址零取指。它写入的保存的计数器和保存的状态是打乱的，因为数据手册说它们的值未定义。它耗费数据手册要求的两个周期的空取指，加上异常进入的三个周期，这五个周期计入 `cycles` 和 `tally`：

```python
from arm6 import Cpu

cpu = Cpu("arm60", fill=0).reset()

print(cpu.registers.pc, cpu.mode.name, cpu.cycles, cpu.steps)
```

```
0 svc32 5 0
```

计数器位于复位向量，时钟已经前进，而指令计数没有。本仓库中只有一处改为手动设置计数器：语料库运行器。原因是录制的用例声明了计数器、模式和中断禁止位，而复位会破坏待比较的状态。

## 它是否正确

三项检查约束着它，其中没有一项是拿本包与自身比较。

**数据手册，引用并核对。** [`conformance/hardware.json`](conformance/hardware.json) 中的每个事实都附有其出处的句子和页码。`python3 -m conformance.quotes` 将全部 **62** 句定位到它们所引用的页面上。ARM60 数据手册没有文本层：`pdftotext` 对其八十三页只返回八十三个字符。因此 [`conformance/quotes.py`](conformance/quotes.py) 用 `pdftoppm` 渲染每个被引用的页面，用 `tesseract` 识别，并按一句引文的五词窗口有多少出现在该页上为其打分。

**经过筛选的语料库，只比对状态。** `python3 -m conformance.singlestep` 运行来自 `SingleStepTests/ARM7TDMI` 的 **424,220** 个录制用例，按提交固定版本，并在每个用例之后比对完整的处理器状态。不一致为 **0** 处。该语料库录制自一个更晚的器件，因此其 1,000,000 个 ARM 状态用例中有 575,780 个被筛除。[`conformance/suites.json`](conformance/suites.json) 中的每一项排除都写明了其依据的句子。不读取任何周期、访问或事务顺序字段：ARM60 乘法的最坏情况是 `1S+16I`，而 ARM7TDMI 是 `1S+4I`，所以那个器件的事务流描述的是另一种总线。

**周期表。** 每种指令形式的开销都由各模块旁边的测试对照 Table 20 进行检查。除总数外，总线记录也会比对，因为模型可能耗费了正确的周期数，却驱动了错误的地址。

尚未解决的问题见 [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md)，各文档之间的分歧见 [`conformance/divergences.json`](conformance/divergences.json)。第一个未决问题是凌驾于这一切之上的上限：这里没有任何内容基于对真实硅片的测量。

| 命令                                       | 参数                                                                                                                                      | 退出码                                                                                 |
| :----------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------- |
| `python3 arm6/doctor.py`                   | 无                                                                                                                                        | 所有检查都通过时为 0，否则为 1                                                         |
| `python3 -m conformance.quotes`            | 无                                                                                                                                        | 所有可读取的引文都已定位时为 0，否则为 1。机器上没有文档时不检查任何内容，并说明这一点 |
| `python3 -m conformance.singlestep [path]` | 语料库的 `v1` 目录，默认为 `external/ARM7TDMI/v1`。`--limit N` 指定每个文件的用例数，`--count` 只计数不比对，`--files` 打印需要获取的路径 | 无不一致或无语料库时为 0，有任何不一致时为 1                                           |
| `python3 -m conformance.speed`             | `--cycles N`，默认为 200,000，以及 `--repeats N`，默认为 7                                                                                | 高于下限时为 0，低于下限时为 1，选项错误时为 2                                         |
| `python3 -m conformance.documents`         | `--check` 只验证不下载，`--only SUBSTRING` 选择文档                                                                                       | 所有文档都验证通过时为 0，否则为 1                                                     |
| `python3 -m conformance.links`             | 无。它探测本 README 中的每个地址                                                                                                          | 除非某个地址返回 404 或 410，否则为 0                                                  |
| `python3 -m conformance.package <wheel>`   | 一个构建好的 wheel                                                                                                                        | 所有模块都已打包且未打包任何测试时为 0，否则为 1，无参数时为 2                         |

## 参与开发

| 需求                             | 位置                                                            |
| :------------------------------- | :-------------------------------------------------------------- |
| 每项门禁检查及其运行顺序         | [CONTRIBUTING.md](CONTRIBUTING.md)                              |
| 面向编程代理的相同内容           | [AGENTS.md](AGENTS.md)                                          |
| 本仓库与家族中其他仓库共享的标准 | [FAMILY.md](FAMILY.md)                                          |
| 缺陷报告                         | [GitHub Issues](https://github.com/gufranco/arm6-python/issues) |
| 安全报告                         | [SECURITY.md](SECURITY.md)                                      |

```bash
uvx ruff@0.16.3 format --check .
uvx ruff@0.16.3 check .
uvx mypy@1.14.1
python3 arm6/core.test.py
```

每个模块旁边都有一个以其命名的测试文件，每个测试文件都可以像上面那样单独运行。覆盖率是一项硬性门禁检查，要求 100% 语句和分支覆盖率。`python3 -m conformance.speed` 是吞吐量下限，在覆盖率步骤之外运行，因为覆盖率追踪器的开销约为模型本身的十倍。

## 参考文献

这些文档都不可再分发，也都不在本仓库中。个别句子引用在 [`conformance/hardware.json`](conformance/hardware.json) 中，并附有其所在的页码。每行给出页数以及文件 SHA-256 的前十六个十六进制数字。

| 文档                                                                                                                                                                | 日期    | 页数 | SHA-256            |
| :------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :------ | ---: | :----------------- |
| [GEC Plessey Semiconductors，_ARM60 Datasheet_，Issue 0.81](https://3dodev.com/_media/documentation/hardware/arm60_datasheet_-_gec_plessey_semiconductors.pdf)      | 1993    |   83 | `315dbff7b6259a73` |
| [Advanced RISC Machines，_ARM610 Data Sheet_，ARM DDI 0004D](https://bitsavers.org/pdf/acorn/ARM_DDI_0004D_ARM610_Data_Sheet_Aug93.pdf)                             | 1993-08 |  134 | `76f13ffe2bc20774` |
| [Advanced RISC Machines，_Application Note 11: Differences Between ARM6 and Earlier ARM Processors_](https://home.marutan.net/rpcemu/Apps11vC.html)                 | 无日期  |    1 | `41239bc21c8e3375` |
| [ARM Limited, _ARM Architecture Reference Manual_, ARM DDI 0100E](https://www.cl.cam.ac.uk/teaching/0405/ECADArch/datasheets/arm.pdf)                               | 2000    |  811 | `fa405a69d371c533` |
| [VLSI Technology, _Acorn RISC Machine (ARM) Family Data Manual_](https://bitsavers.mirrorservice.org/components/vti/1990_Acorn_RISC_Machine_Family_Data_Manual.pdf) | 1990    |  322 | `f3a524aeec44ab45` |

[`conformance/documents.json`](conformance/documents.json) 为每份文档记录完整摘要、字节数和一个可获取的地址。`python3 -m conformance.documents` 将五份文档全部下载到 git 忽略的 `docs/` 中，并拒绝摘要不符的文件。`--check` 验证已经存在的副本。清单从一个镜像获取 ARM610 数据手册，因为上面链接的地址对普通获取请求返回 403。两者提供的字节相同。

以 ARM60 数据手册为准。它是已找到的唯一一份按指令、按周期给出该器件总线行为的文档。ARM610 数据手册是指令集和程序员模型的第二个佐证，仅此而已：它的总线章节描述的是两个时钟、两种周期类型和一个缓存。Application Note 11 是已找到的唯一一份印有四种 26 位模式编码的文档，两份数据手册都没有收录这些编码。ARM DDI 0100E 印有立即数循环移位后的移位器进位，ARM60 数据手册没有给出这一点。VLSI 数据手册是为 ARM2aS 宏单元而读的，它描述的是其他器件，因此在这里不决定任何事。

[SingleStepTests/ARM7TDMI](https://github.com/SingleStepTests/ARM7TDMI) 提供录制用例。其提交和每一项筛选条目都在 [`conformance/suites.json`](conformance/suites.json) 中。

## 引用本项目

[CITATION.cff](CITATION.cff) 在每次发布时，由写入包版本号的脚本更新。

## 许可证

MIT。见 [LICENSE](LICENSE)。

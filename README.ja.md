# ARM6

Pythonで書かれたARM60プロセッサです。1命令または1バスサイクルずつ進みます。すべての命令とそれが費やすすべてのサイクルはGEC Plessey ARM60データシートに、各命令後のプロセッサ状態はフィルタ済みのARM7TDMIコーパスに照らして検証されています。

[English](README.md) | 日本語 | [简体中文](README.zh-Hans.md) | [繁體中文（香港）](README.zh-HK.md)

[![CI](https://github.com/gufranco/arm6-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/arm6-python/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gufranco/arm6-python)](https://github.com/gufranco/arm6-python/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

記録ケース**424,220**件を比較、不一致**0**件、引用文**62**件を出典ページ上で照合、パーツ**1**種、テスト**1,181**件、ステートメントとブランチのカバレッジ**100%**、依存関係なし

```python
from arm6 import Cpu, Memory

cpu = Cpu("arm60", Memory(image=(0xE3A0002A).to_bytes(4, "little"), fill=0)).reset()

spent = cpu.step()

print(f"{cpu.registers.read(0):#010x} in {spent} cycle, {cpu.spent}")
```

```
0x0000002a in 1 cycle, Cycles(s=1, n=0, i=0, c=0)
```

イメージには`mov R0, #42`の1ワードが入っています。`reset()`はプログラムカウンタをアドレス0に向け、`step()`はその1命令を実行します。コストは1シーケンシャルサイクルで、これはTable 20がデータ処理命令に与える値です。`spent`はそのコストをデータシートの4つのサイクル種別S、N、I、Cに分けて保持します。

## インストール

| 要件                    | バージョン                                          |
| :---------------------- | :-------------------------------------------------- |
| Python                  | 3.12以降                                            |
| git                     | 任意                                                |
| `pdftoppm`と`tesseract` | 任意。`python3 -m conformance.quotes`でのみ必要です |

```bash
git clone https://github.com/gufranco/arm6-python.git
cd arm6-python
python3 arm6/doctor.py
```

このパッケージは標準ライブラリ以外を何もインポートしません。`pip install git+https://github.com/gufranco/arm6-python.git`を使うとチェックアウトなしでインストールでき、同じドクターを実行する`arm6-doctor`コマンドが追加されます。

ドクターはマシンとチェックアウトを確認し、パーツを1つ構築してステップ実行し、最後に1行を出力します。すべてのチェックに合格すると0で、そうでなければ1で終了します。バグ報告には出力全体を貼り付けてください。

```
  5 checks, nothing to report
```

`pdftoppm`または`tesseract`がないマシンでは、最後の行は`1 of 5 checks did not pass`になります。その場合も引用チェッカー以外はすべて動作します。

リリースは[Semantic Versioning](https://semver.org/)に従い、semantic-releaseによってコミット履歴から作成されます。すべてのリリースにはタグが付けられ、[リリースページ](https://github.com/gufranco/arm6-python/releases)に掲載されます。

## インターフェース

`arm6.Cpu(model, memory=None, seed=UNSET_SEED, fill=None, bigend=False, lateabt=True)`はパーツを1つ構築します。

| 引数      | 意味                                                                                                                                                   |
| :-------- | :----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `model`   | 必須です。`arm60`またはその別名`arm6`で、大文字小文字は問いません。デフォルトはありません                                                              |
| `memory`  | `read_byte`、`write_byte`、`read_word`、`write_word`を持つ任意のオブジェクトです。省略すると、パーツは`seed`、`fill`、`bigend`から`Memory`を構築します |
| `seed`    | レジスタと、パーツが構築するメモリの電源投入時の内容を決めます                                                                                         |
| `fill`    | 代わりにすべてのレジスタと未書き込みのすべてのバイトの初期値となる値です。`fill=0`で静かな状態から始まります                                           |
| `bigend`  | `bigend`ピンです。パーツが構築するメモリに渡され、`memory`が与えられた場合は無視されます                                                               |
| `lateabt` | `lateabt`ピンで、パーツに保持されます。アボートピンは駆動されないため、何も変わりません                                                                |

### 呼び出し

| 呼び出し                             | 効果                                                                                                                                                                                                                                                                      | 戻り値                              |
| :----------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :---------------------------------- |
| `reset(low_cycles=2)`                | Section 6.3.6に従い、スーパーバイザモードにし、両方の割り込み禁止を設定し、アドレス0からフェッチします。リセットラインを`low_cycles`回のダミーフェッチの間保持します。2回未満にはなりません。その後例外エントリに3サイクルを費やすため、デフォルトでは5サイクルかかります | パーツ                              |
| `step()`                             | 1命令、または保留中のFIQやIRQへのエントリです                                                                                                                                                                                                                             | 費やしたサイクル数を`int`で返します |
| `run_for(cycles)`                    | 少なくとも`cycles`を費やすまで命令単位で実行します。命令は分割されないため、超過することがあります                                                                                                                                                                        | 費やしたサイクル数                  |
| `run_until(check, limit=None)`       | `check(cpu)`が偽の間ステップ実行します。`limit`命令後に`RunLimit`を送出します                                                                                                                                                                                             | パーツ                              |
| `held()`                             | パーツが進行を停止したかどうかです。このパーツを止めるものはありません                                                                                                                                                                                                    | `False`                             |
| `irq(level=True)`、`fiq(level=True)` | ラインを設定します。禁止ビットがクリアされていれば、次の`step()`がそれを受け付けます                                                                                                                                                                                      | 今受け付けられるかどうか            |

### 状態

| 属性                        | 意味                                                                                                                                                                                                                                                                                  |
| :-------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `model`                     | `Model`レコードです。`name`、`aliases`、`summary`を持ちます                                                                                                                                                                                                                           |
| `memory`                    | メモリオブジェクトです                                                                                                                                                                                                                                                                |
| `registers`                 | `Registers`です。`read(index)`、`write(index, value)`、`pc`、`cpsr`、`saved()`、`save(value)`、`mode`を持ちます                                                                                                                                                                       |
| `mode`                      | CPSRから読み取った現在の`Mode`です                                                                                                                                                                                                                                                    |
| `cycles`                    | パーツの構築以降のサイクル数で、リセットを含みます                                                                                                                                                                                                                                    |
| `steps`                     | 最後のリセット以降の命令数です                                                                                                                                                                                                                                                        |
| `spent`                     | 最後の命令のコストを`Cycles`で表したものです                                                                                                                                                                                                                                          |
| `tally`                     | 累計を`Cycles`で表したもので、リセットをまたいで保持されます                                                                                                                                                                                                                          |
| `bus.cycles`                | 最後の命令のバスサイクルごとに1つの`Cycle`です。`kind`、`address`、`nopc`、`nbw`、`nrw`、`ntrans`、`lock`、`data`を持ちます。`kind`はコプロセッサを接続しないパーツが駆動する表3のサイクルタイプ（N、S、I）のいずれかで、`letter`、`name`、`nmreq`、`seq`、`touches_memory`を持ちます |
| `irq_line`、`fiq_line`      | 各割り込みラインのレベルです                                                                                                                                                                                                                                                          |
| `on_cycle`                  | 各バスサイクルの終わり、そのサイクルの処理の後に、パーツを引数として呼ばれる呼び出し可能オブジェクト、または`None`です。`Clock`がこれを設定します                                                                                                                                     |
| `seed`、`bigend`、`lateabt` | コンストラクタの引数です                                                                                                                                                                                                                                                              |

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

このプログラムはR0を3まで数え、その後自分自身へ分岐します。10命令のコストは14サイクルで、リセットの5サイクルを加えて19になります。`run_for(10)`は3サイクルの分岐を4回実行し、12を報告します。各分岐は非シーケンシャルフェッチを1回、シーケンシャルフェッチを2回行います。リセットでIビットがセットされたままなので、`irq()`は`False`を返します。

### メモリ、レジスタ、モード

`arm6.Memory(image=None, seed=UNSET_SEED, fill=None, bigend=False)`は4 GBの疎なメモリです。`image`はアドレス0から書き込まれます。誰も書き込んでいないバイトは`fill`として読まれ、`fill`が`None`の場合は`seed`とアドレスから導かれた値として読まれます。呼び出しは`read_byte`、`write_byte`、`read_word`、`write_word`です。ワードアクセスはアドレスの下位2ビットを無視します。`written`は書き込まれたすべてのアドレスをそのバイトに対応付けます。

`arm6.Registers`は31個の汎用レジスタと6個のステータスレジスタを保持します。`read(15)`は下位2ビットをクリアしたプログラムカウンタを返します。

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

`bigend`を設定すると、同じ4バイトが別のワードとして読まれます。0x2002に書き込んだワードは0x2000に置かれます。2つのシードは異なる電源投入時のバイトを与えます。リセット後のCPSRは`0xd3`で、これはIビットとFビットがセットされたスーパーバイザモードです。

| 名前              | 内容                                                                                                                                                                                                               |
| :---------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `arm6.MODES`      | 名前をキーとする10個の`Mode`レコードです。`usr32`、`fiq32`、`irq32`、`svc32`、`abt32`、`und32`と、26ビットの`usr26`、`fiq26`、`irq26`、`svc26`です。それぞれ`bits`、`wide`、`privileged`、`bank`、`spsr`を持ちます |
| `arm6.VECTORS`    | 名前ごとの7つの例外ベクタで、0x00の`reset`から0x1Cの`fiq`までです                                                                                                                                                  |
| `arm6.UNSET_SEED` | シードが与えられないときに使われるシードです                                                                                                                                                                       |

### カタログとエラー

| 名前                       | 内容                                                                                                                                                                                |
| :------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `arm6.MODELS`              | `arm60`をキーとする1つの`Model`レコードです                                                                                                                                         |
| `arm6.Model`               | カタログのエントリです。属性への書き込みはすべて拒否します                                                                                                                          |
| `arm6.Arm6Error`           | 以下のすべてのエラーの基底です                                                                                                                                                      |
| `arm6.UnknownModelError`   | どのモデルにも該当しない名前や空の名前に対して`Cpu`が送出します。メッセージには受け付けるすべての名前が列挙されます                                                                 |
| `arm6.RunLimit`            | `check`が成り立たないまま`limit`命令が経過したときに`run_until`が送出します                                                                                                         |
| `arm6.EmptyRegisterList`   | レジスタが1つも指定されていないブロック転送に対して`step`が送出します。Section 7.9はこれを禁止しており、パーツがどう動作するかは述べていません                                      |
| `arm6.UnspecifiedEncoding` | Figure 28のどの行にも一致しないワードに対して`step`が送出します                                                                                                                     |
| `arm6.NoCoprocessor`       | 公開されていますが、送出されることはありません。コプロセッサ命令は未定義命令トラップに入ります。これはコプロセッサが接続されていない場合についてSection 10.15が述べているとおりです |
| `arm6.UnknownMode`         | CPSRのモードフィールドが10個のモードのいずれでもないときに送出されます                                                                                                              |
| `arm6.WaitsRequired`       | `Cycles.ticks(None)`が送出します                                                                                                                                                    |
| `arm6.BadWaits`            | 1未満の値に対して`Waits`が送出します                                                                                                                                                |
| `arm6.ClockClosed`         | `close()`の後に`Clock.tick()`が送出します                                                                                                                                           |
| `arm6.Truncated`           | オフセットに残っているバイトが4バイト未満のときにデコーダが送出します。`offset`がその位置を保持します。`disassemble`は送出せず、そこでリストを終えます                              |
| `arm6.__version__`         | インストールされているバージョンです                                                                                                                                                |

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

名前は大文字小文字を問わず照合されます。リストが空のブロック転送と、Figure 28に該当する行がないワードは、推測されずに拒否されます。コプロセッサ命令は、アドレス4のベクタで未定義モードに入ります。

## 実際の速度で動かす

`step`はサイクル数を報告します。それにどれだけの時間がかかったかは示しません。

```python
from arm6 import Cpu, Waits

cpu = Cpu("arm60", fill=0).reset()
cpu.step()

print(cpu.spent.ticks(Waits(sequential=1, nonsequential=3, internal=1, coprocessor=1)))
```

```
1
```

Section 8.6によると、`mclk`は制限なく引き伸ばすことができ、代わりに`Nwait`でサイクル単位の待ちを挿入することもできます。ピン表は、待ちを必要としないシステムでは`Nwait`をHIGHに固定してよいと付け加えています。したがって、1サイクルにかかる時間はボードに関する事実です。`Waits`はボードを1つ記述します。各サイクル種別が費やす`mclk`周期数で、それぞれ1以上です。`Cycles.ticks(waits)`は4つのカウントにそれらの値を掛けます。ボードを指定せずにティック数を求めると拒否されます。

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

`Cycles`は`s`、`n`、`i`、`c`、`total`を持ち、別の`Cycles`と加算でき、属性への書き込みはすべて拒否します。`total`は、ピン表が明示している唯一の構成、すなわち`Nwait`をHIGHに固定し1サイクルあたり`mclk`1周期とする構成でのティック数でもあります。

## 1サイクルずつ駆動する

`step`は命令全体を実行します。`arm6.Clock(cpu)`はパーツをスレッド上で実行し、バスサイクルごとにブロックするため、呼び出し側は1命令の2つのサイクルの間で止めることができます。

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

最初のワードはアドレス8へのリンク付き分岐で、3サイクルかかります。2サイクル後にはカウンタはすでに分岐先を指しており、3番目のサイクル、つまり2回目のリフィルフェッチはまだ起きていません。`Cpu.run_for`は命令単位でサイクルを費やすため、そこで止まることはできません。

| Clockの呼び出し           | 効果                                                                                                          | 戻り値     |
| :------------------------ | :------------------------------------------------------------------------------------------------------------ | :--------- |
| `tick()`                  | パーツに1バスサイクルを実行させます。`close()`の後は`ClockClosed`を送出し、パーツが送出したものは再送出します | サイクル数 |
| `run_for(cycles)`         | `cycles`回ティックします                                                                                      | サイクル数 |
| `close()`                 | スレッドを停止し、パーツの`on_cycle`を元に戻します。`with`ブロックがこれを呼び出します                        | `None`     |
| イテレーション            | クロックが閉じられるまで、各ステップが1回の`tick()`です                                                       | サイクル数 |
| `cycles`、`closed`、`cpu` | これまでのティック数、閉じられているかどうか、駆動しているパーツです                                          |            |

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

`fill=0`では、すべてのワードが1サイクルの`andeq`です。4回のティックで4命令を実行します。ティックはそのサイクルの処理がすべて終わってから止まるため、その後クロックを閉じても閉じなくても、パーツは`step()`を4回呼んだときと同じ状態です。

## モデル

```python
from arm6 import MODELS, Cpu

print(sorted(MODELS))
print(Cpu("arm60").model.name, Cpu("arm6").model.name, Cpu("ARM60").model.name)
```

```
['arm60']
arm60 arm60 arm60
```

`arm60`が名前で、`arm6`はその別名です。カタログのエントリは1つだけですが、どのモデルにも該当しない名前は拒否し、受け付けるすべての名前を列挙します。

コアはARM60、ARM600、ARM610で同じです。ARM610データシートは、ARM610内のCPUはARM6であると述べ、ARM600との差分としてバスとパッケージに関する5つの違いを挙げています。バスは異なり、このパッケージはクロック駆動のパーツをバスまでモデル化しています。バスをサイクルごとに示す文書があるのはARM60だけなので、ここにあるのはARM60だけです。ARM600、ARM610、ARM61は、欠けている各文書が何を決着させるかとともに[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md)にあります。

## 実行せずに読む

`arm6.disassemble(data, offset=0, address=0, count=None, stop_at_return=False)`はワードを実行せずに読みます。次はステータスビットを待ってから1バイトを読むルーチンです。

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

各結果は`arm6.Instruction`で、`address`、`offset`、`word`、`condition`、`mnemonic`、`kind`、`operand`、`size`、`text`を持ちます。`condition`と`kind`はデータシートの名前を使います。`operand`はオペランドフィールドが表す1つの数値で、アドレッシングが自己完結している場合はアドレスに解決されます。

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

プログラムカウンタ相対のロードは、そのリテラルが置かれているアドレス0x800Cを報告し、32780と表示されます。`mov`は数値を持たないため、その`operand`は`None`です。`count`はその数のワードの後で停止します。1ワードに満たない末尾の断片でリストは終わります。

`disassemble`は先頭から順に読み、何もたどりません。あるワードがコードかどうかは、制御がどのようにそこへ到達したかに依存するからです。このパーツには復帰命令がなく、どの命令でも書き込めるプログラムカウンタがあるだけです。`stop_at_return`は、コンパイラが復帰のために出力する2つの形、`mov PC, LR`とPCをロードする`ldm`の後で停止し、それ以外では停止しません。

11種類の`kind`はFigure 28の行です。この図には、分岐と交換の行、ハーフワード転送の行、符号付きロードの行、ロング乗算の行がありません。どの行にも一致しないワードは、推測されずに`unspecified`として報告されます。

## クリーンな状態からは始まらない

```python
from arm6 import Cpu

cpu = Cpu("arm60", seed=7)

print(cpu.registers.read(0) != 0, cpu.registers.pc != 0)
```

```
True True
```

構築時には、プログラムカウンタを含むすべてのレジスタが`seed`から導かれた状態に置かれます。リセット前にステップ実行されたパーツは、電源投入後のシリコンと同じように、そのアドレスから実行します。

`reset()`は呼び出し側が既知の状態を得る方法であり、上のすべての例はこれで始まっています。これはSection 6.3.6が列挙するもの、すなわちスーパーバイザモード、両方の割り込み禁止、アドレス0からのフェッチだけを書き込みます。書き込まれる退避済みのカウンタとステータスは、データシートがその値は定義されていないと述べているため、ランダム化されます。データシートが要求するダミーフェッチの2サイクルに例外エントリの3サイクルを加えたコストがかかり、その5サイクルは`cycles`と`tally`に反映されます。

```python
from arm6 import Cpu

cpu = Cpu("arm60", fill=0).reset()

print(cpu.registers.pc, cpu.mode.name, cpu.cycles, cpu.steps)
```

```
0 svc32 5 0
```

カウンタはリセットベクタにあり、クロックは進み、命令数は進んでいません。このリポジトリでは1か所だけ、代わりにカウンタを手で設定しています。コーパスランナーです。記録されたケースはカウンタ、モード、割り込み禁止を宣言しており、リセットすると比較対象の状態が壊れてしまうからです。

## 正しいのか

3つのチェックがこれを支えており、いずれもパッケージをそれ自身と比較するものではありません。

**データシートの引用と検証。** [`conformance/hardware.json`](conformance/hardware.json)のすべての事実は、その出典となった文とページを持っています。`python3 -m conformance.quotes`は**62**件すべてを、それぞれが引用するページ上で照合します。ARM60データシートにはテキストレイヤーがありません。`pdftotext`は83ページに対して83文字しか返しません。そのため[`conformance/quotes.py`](conformance/quotes.py)は、引用された各ページを`pdftoppm`で画像化し、`tesseract`で読み取り、引用の5語ウィンドウのうちいくつがそのページに現れるかで引用を採点します。

**フィルタ済みのコーパス、状態のみ。** `python3 -m conformance.singlestep`は、コミットで固定された`SingleStepTests/ARM7TDMI`の記録ケース**424,220**件を実行し、各ケースの後のプロセッサ状態全体を比較します。不一致は**0**件です。このコーパスは後のパーツから記録されたものなので、1,000,000件あるARMステートのケースのうち575,780件は除外されています。[`conformance/suites.json`](conformance/suites.json)の各除外項目には、その根拠となる文が記されています。サイクル、アクセス、トランザクション順序のフィールドは一切読みません。ARM60の乗算の最悪ケースは`1S+16I`で、ARM7TDMIは`1S+4I`であり、そのパーツのトランザクション列は別のバスを記述しているからです。

**サイクル表。** すべての命令形式のコストは、各モジュールの隣にあるテストによってTable 20に照らして検証されています。合計だけでなくバスの記録も比較します。モデルは正しいサイクル数を費やしながら誤ったアドレスを駆動することがあるからです。

決着していないことは[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md)に、文書どうしの食い違いは[`conformance/divergences.json`](conformance/divergences.json)にあります。最初の未解決の問いは、これらすべての上限です。ここにあるものは何一つ、実際のシリコンの測定に基づいていません。

| コマンド                                   | 引数                                                                                                                                                                          | 終了コード                                                                                                             |
| :----------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------- |
| `python3 arm6/doctor.py`                   | なし                                                                                                                                                                          | すべてのチェックに合格すれば0、そうでなければ1                                                                         |
| `python3 -m conformance.quotes`            | なし                                                                                                                                                                          | 読み取れたすべての引用が照合されれば0、そうでなければ1。マシン上に文書がない場合は何もチェックせず、その旨を表示します |
| `python3 -m conformance.singlestep [path]` | コーパスの`v1`ディレクトリで、デフォルトは`external/ARM7TDMI/v1`です。`--limit N`でファイルごとのケース数、`--count`で比較せずに数える、`--files`で取得すべきパスを表示します | 不一致がないかコーパスがなければ0、不一致があれば1                                                                     |
| `python3 -m conformance.speed`             | `--cycles N`はデフォルトで200,000、`--repeats N`はデフォルトで7です                                                                                                           | 下限を上回れば0、下回れば1、不正なオプションでは2                                                                      |
| `python3 -m conformance.documents`         | `--check`で取得せずに検証、`--only SUBSTRING`で文書を選択します                                                                                                               | すべての文書が検証されれば0、そうでなければ1                                                                           |
| `python3 -m conformance.links`             | なし。このREADME内のすべてのアドレスを確認します                                                                                                                              | アドレスが404または410を返さない限り0                                                                                  |
| `python3 -m conformance.package <wheel>`   | ビルド済みのwheel                                                                                                                                                             | すべてのモジュールが含まれ、テストが1つも含まれていなければ0、そうでなければ1、引数がなければ2                         |

## 開発に参加する

| 必要なもの                                               | 場所                                                            |
| :------------------------------------------------------- | :-------------------------------------------------------------- |
| すべてのゲートとその実行順序                             | [CONTRIBUTING.md](CONTRIBUTING.md)                              |
| コーディングエージェント向けの同じ内容                   | [AGENTS.md](AGENTS.md)                                          |
| このリポジトリがファミリーの他のリポジトリと共有する標準 | [FAMILY.md](FAMILY.md)                                          |
| バグ報告                                                 | [GitHub Issues](https://github.com/gufranco/arm6-python/issues) |
| セキュリティ報告                                         | [SECURITY.md](SECURITY.md)                                      |

```bash
uvx ruff@0.16.3 format --check .
uvx ruff@0.16.3 check .
uvx mypy@1.14.1
python3 arm6/core.test.py
```

各モジュールには、その隣に同じ名前に基づくテストファイルがあり、上のようにそれぞれ単独で実行できます。カバレッジはステートメントとブランチで100%の厳格なゲートです。`python3 -m conformance.speed`はスループットの下限であり、カバレッジのステップの外で実行されます。カバレッジトレーサーはモデル自体の約10倍のコストがかかるからです。

## 参考文献

これらの文書はいずれも再配布可能ではなく、このリポジトリには含まれていません。個々の文は、印刷されているページとともに[`conformance/hardware.json`](conformance/hardware.json)に引用されています。各行にはページ数と、ファイルのSHA-256の先頭16桁の16進数を示しています。

| 文書                                                                                                                                                                | 日付     | ページ数 | SHA-256            |
| :------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :------- | -------: | :----------------- |
| [GEC Plessey Semiconductors, _ARM60 Datasheet_, Issue 0.81](https://3dodev.com/_media/documentation/hardware/arm60_datasheet_-_gec_plessey_semiconductors.pdf)      | 1993     |       83 | `315dbff7b6259a73` |
| [Advanced RISC Machines, _ARM610 Data Sheet_, ARM DDI 0004D](https://bitsavers.org/pdf/acorn/ARM_DDI_0004D_ARM610_Data_Sheet_Aug93.pdf)                             | 1993-08  |      134 | `76f13ffe2bc20774` |
| [Advanced RISC Machines, _Application Note 11: Differences Between ARM6 and Earlier ARM Processors_](https://home.marutan.net/rpcemu/Apps11vC.html)                 | 日付なし |        1 | `41239bc21c8e3375` |
| [ARM Limited, _ARM Architecture Reference Manual_, ARM DDI 0100E](https://www.cl.cam.ac.uk/teaching/0405/ECADArch/datasheets/arm.pdf)                               | 2000     |      811 | `fa405a69d371c533` |
| [VLSI Technology, _Acorn RISC Machine (ARM) Family Data Manual_](https://bitsavers.mirrorservice.org/components/vti/1990_Acorn_RISC_Machine_Family_Data_Manual.pdf) | 1990     |      322 | `f3a524aeec44ab45` |

[`conformance/documents.json`](conformance/documents.json)には、各文書の完全なダイジェスト、バイト数、取得可能なアドレスが記載されています。`python3 -m conformance.documents`は5つすべてをgitが無視する`docs/`にダウンロードし、ダイジェストが異なるファイルは拒否します。`--check`はすでにあるコピーを検証します。上にリンクしたアドレスは単純な取得に403を返すため、マニフェストはARM610データシートをミラーから取得します。どちらも同じバイト列を提供します。

判断の基準はARM60データシートです。このパーツのバスを命令ごと、サイクルごとに示している文書は、見つかった中でこれだけです。ARM610データシートは命令セットとプログラマモデルについての第2の証拠であり、それ以外には使いません。そのバスの章は2つのクロック、2つのサイクル種別、キャッシュを記述しているからです。Application Note 11は、両方のデータシートが省いている4つの26ビットモードのエンコーディングを記載している、見つかった中で唯一の文書です。ARM DDI 0100Eは、ARM60データシートが省いている即値ローテート後のシフタのキャリーを記載しています。VLSIのデータマニュアルはARM2aSマクロセルを求めて読みましたが、別のパーツを記述しているため、ここでは何も決めません。

[SingleStepTests/ARM7TDMI](https://github.com/SingleStepTests/ARM7TDMI)が記録ケースを提供しています。そのコミットとすべてのフィルタ項目は[`conformance/suites.json`](conformance/suites.json)にあります。

## 引用

[CITATION.cff](CITATION.cff)は、パッケージのバージョンを刻むスクリプトによってリリースごとに更新されます。

## ライセンス

MITです。[LICENSE](LICENSE)を参照してください。

# Japanese pack — terminology glossary

Working glossary for the ja-JP UI. **Data names** (monsters, skills, items) are not
listed here: they are generated from the game's own Japanese text
(`scripts/gen_names_ja.py` → `dashboard/locales/ja/data.json`), so they cannot
drift from what players see in game. This file covers the vocabulary *we*
chose for the interface and the reasoning behind it.

Sources, in priority order:

1. **The game's own text** — HunterPie's `ja-jp.xml` (MIT, mirrored from the
   game strings) for monsters and skills; the results-screen names for awards
   come from the game at capture time.
2. **[kiranico /ja](https://mhwilds.kiranico.com/ja)** — cross-check for
   monsters, weapon classes, skills and items. Verified: its monster names are
   identical to `ja-jp.xml` (リオレイア, リオレウス, 護竜リオレウス, …). It has
   **no page for the 30 quest-end awards** (its "awards" are 勲章 guild-card
   medals, a different system), which is why those need a native reviewer.
3. **The reviewer** — final say on UI sentence wording.

## Core vocabulary

| English | 日本語 | Notes |
| --- | --- | --- |
| hunt / run | ハント | the unit of data; never 狩猟 for the noun in UI |
| hunt (verb) | 狩る | only in prose |
| quest | クエスト | as in game |
| hunter | ハンター | player character |
| party | パーティ | 4-hunter group |
| supporter | サポート | CPU companions; club in-game term |
| hunter rank | ハンターランク | not ハンターランク（HR）in tight cells |
| clear rate | クリア率 | |
| cleared / failed | クリア / 失敗 | |
| cart | 力尽き | count → 力尽き回数 |
| damage | ダメージ | |
| damage share | ダメージシェア | |
| DPS | DPS | left Latin, never 毎秒ダメージ |
| HP | HP | |
| uptime | 維持時間 | buffs/debuffs |
| time in danger | 危険時間 | survival tab |
| enrage | 怒り状態 | as in game |
| ailment | 状態異常 | |
| weak point | 弱点 | |
| highlight / award | 褒賞 | game calls the results-screen list 褒賞; "ハイライト" is the tab name only |
| weapon | 武器 | |
| weapon class | 武器種 | |
| build / weapon variant | ビルド | gear-fingerprint grouping |
| gear | 装備 | |
| stars | ★ | keep the glyph, no word |
| crown | 冠 | 金冠 / 銀冠 / 最小冠 |
| monster | モンスター | |

## Weapon classes (mirrors `locales/ja/names.json`)

大剣 · 片手剣 · 双剣 · 太刀 · ハンマー · 狩猟笛 · ランス · ガンランス ·
スラッシュアックス · チャージアックス · 操虫棍 · 弓 · ヘビィボウガン ·
ライトボウガン

## Style rules

- Politeness: plain UI register (`です・ます` only in explanatory hints, not in
  labels or buttons). Buttons are noun/short verb forms: 閉じる, 追加, 保存.
- No trailing period on labels, buttons, table headers or chart ticks.
- Numbers: `Intl` with `ja-JP`; dates as `YYYY/MM/DD`.
- Parenthetical clarifications use full-width parentheses （…）, but keep them
  short — prefer a line of hint text over a long parenthetical.
- Keep `{n}`/`{hunts}`-style placeholders byte-identical and in a position
  that reads naturally.
- Do not translate: player names, weapon model names ("Onyx Choros"), file
  paths, `$HUNT_EXPORTS`, brands (HunterPie, REFramework, HuntDumper, Nexus,
  GitHub), units already in Latin (DPS, HP, HR).

## Open questions for the reviewer

1. **Quest awards** — confirm the in-game Japanese names for the 30 results-screen
   awards (Support All-Star, Perfect Counters, Clasher, …). The app currently
   stores whatever the game wrote at capture time, so a Japanese game produces
   Japanese awards; the hand-written table only covers English-captured history.
2. **褒賞 vs ハイライト** — is 褒賞 right for the per-hunt list, with ハイライト
   reserved for the tab name?
3. **力尽き** vs 乙 — 力尽き is official; confirm it fits a stats column.

## Quest awards — names needed

The 30 results-screen awards are captured in the language the game was running
in, so a Japanese game already produces Japanese names for new hunts, while
hunts recorded on an English game keep English names. The right-hand column
below is the checked-in table (`dashboard/locales/ja/data.json`, `awards`):
**literal first-pass translations, not verified against the game.** Please
correct any that differ from the in-game wording — replace the row's value in
the JSON (all 30 at once, never partially) and re-run
`python scripts/gen_names_ja.py`:

| id | English (captured) | 日本語（ゲーム内表記） |
| --- | --- | --- |
| 0 | Support All-Star | サポートオールスター |
| 1 | Ailment Master | 状態異常マスター |
| 2 | Dizzy Pro | スタンのプロ |
| 3 | Target Destroyer | ターゲットデストロイヤー |
| 4 | Established Hunter | 一流ハンター |
| 5 | Master Mounter | 乗りマスター |
| 6 | Treasure Hunter | トレジャーハンター |
| 7 | Field Researcher | フィールドリサーチャー |
| 8 | Slinger Sniper | スリンガースナイパー |
| 9 | Survival Expert | サバイバルエキスパート |
| 10 | Tool Specialist | ツールスペシャリスト |
| 11 | BBQ King | BBQキング |
| 12 | Master Angler | 釣りマスター |
| 13 | Beast Master | ビーストマスター |
| 14 | Stealth Hunter | ステルスハンター |
| 15 | Gathering Maniac | 採取マニア |
| 16 | Item Addict | アイテム中毒 |
| 17 | Obsessed Observer | 執念の観察者 |
| 18 | Hit 'Em Where It Hurts! | 弱点を突け！ |
| 19 | Beautiful Bombardier | 美しき爆撃手 |
| 20 | Social Butterfly | 社交界の蝶 |
| 21 | Small Game Monster Hunter | 小物モンスターハンター |
| 22 | Slinger Savant | スリンガーの天才 |
| 23 | Seikret Sidestep | セクレトステップ |
| 24 | Perfect Counters | パーフェクトカウンター |
| 25 | Glide Master | 滑空マスター |
| 26 | Dual Wielder | 二刀流 |
| 27 | Assassination | 暗殺 |
| 28 | Weak Point | 弱点 |
| 29 | Clasher | 激突王 |

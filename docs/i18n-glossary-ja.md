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
in, so a Japanese game already produces Japanese names for new hunts. Hunts
recorded on an English game keep English names. To translate that history the
app needs an id → 日本語 table (`dashboard/locales/ja/data.json`, `awards`).
Please fill the right-hand column with the in-game wording:

| id | English (captured) | 日本語（ゲーム内表記） |
| --- | --- | --- |
| 0 | Support All-Star | |
| 1 | Ailment Master | |
| 2 | Dizzy Pro | |
| 3 | Target Destroyer | |
| 4 | Established Hunter | |
| 5 | Master Mounter | |
| 6 | Treasure Hunter | |
| 7 | Field Researcher | |
| 8 | Slinger Sniper | |
| 9 | Survival Expert | |
| 10 | Tool Specialist | |
| 11 | BBQ King | |
| 12 | Master Angler | |
| 13 | Beast Master | |
| 14 | Stealth Hunter | |
| 15 | Gathering Maniac | |
| 16 | Item Addict | |
| 17 | Obsessed Observer | |
| 18 | Hit 'Em Where It Hurts! | |
| 19 | Beautiful Bombardier | |
| 20 | Social Butterfly | |
| 21 | Small Game Monster Hunter | |
| 22 | Slinger Savant | |
| 23 | Seikret Sidestep | |
| 24 | Perfect Counters | |
| 25 | Glide Master | |
| 26 | Dual Wielder | |
| 27 | Assassination | |
| 28 | Weak Point | |
| 29 | Clasher | |

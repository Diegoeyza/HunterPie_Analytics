# Japanese translation review sheet

**Generated file — do not edit in place** (`npm run i18n:sheet` overwrites it).
Review by commenting in the PR/issue, or copy the CSV, fill the `japanese` and
`source` columns, and send it back.

Source: `dashboard/locales/*/` — English is the source of truth for keys.
Flag anything that reads unnaturally in the game's own vocabulary. Placeholders
like `{n}` are filled by the app and must stay in the string.

Terminology source for data names: the game's own text (monsters and skills) and
kiranico (verification). Quest award names are a literal first pass and most need your review.

## App shell, top bar, data-source note, generic buttons
<sub>locales/*/common.json · 24 strings</sub>

| key | English | 日本語 | source |
| --- | --- | --- | --- |
| `app.title` | HunterPie Analytics | HunterPie Analytics |  |
| `app.description` | Post-hunt telemetry dashboard for MH Wilds | MH Wilds のハント後テレメトリダッシュボード |  |
| `app.ingestOnline` | ingestion online · {hunts} hunts | 取り込み稼働中 · {hunts} ハント |  |
| `app.connecting` | connecting… | 接続中… |  |
| `app.dataSource` | Data source | データソース |  |
| `app.hideSourceNote` | Hide data source note | データソースの説明を隠す |  |
| `app.hide` | Hide | 隠す |  |
| `app.sourceNone` | No capture source found — install the REFramework mod and/or the HunterPie analytics fork, then Import. | 取り込み元が見つかりません。REFramework MOD か HunterPie 解析版をインストールしてから「インポート」してください。 |  |
| `app.sourceBoth` | Sources: HunterPie + REFramework (full data). | 取り込み元: HunterPie + REFramework（全データ）。 |  |
| `app.sourceHunterpie` | Source: HunterPie — damage & curves. Quest awards need the REFramework mod. | 取り込み元: HunterPie — ダメージとカーブ。クエスト褒賞には REFramework MOD が必要です。 |  |
| `app.sourceReframework` | Source: REFramework — awards & HP curves. DPS curves need HunterPie. | 取り込み元: REFramework — 褒賞とHPカーブ。DPSカーブには HunterPie が必要です。 |  |
| `app.versions` | HunterPie {hunterpie} · game {game} | HunterPie {hunterpie} · ゲーム {game} |  |
| `common.all` | All | すべて |  |
| `common.none` | None | なし |  |
| `common.close` | Close | 閉じる |  |
| `common.add` | Add | 追加 |  |
| `common.save` | Save | 保存 |  |
| `common.cancel` | Cancel | キャンセル |  |
| `common.remove` | Remove {name} | {name} を削除 |  |
| `common.unknown` | Unknown | 不明 |  |
| `common.loading` | Loading… | 読み込み中… |  |
| `common.retry` | Retry | 再試行 |  |
| `common.copy` | Copy | コピー |  |
| `common.copied` | Copied | コピーしました |  |

## Tab names and one-line descriptions
<sub>locales/*/tabs.json · 26 strings</sub>

| key | English | 日本語 | source |
| --- | --- | --- | --- |
| `tab.progress` | Progress | 進行 |  |
| `tab.progress.blurb` | FR-3.1 — rolling DPS and clear time per hunt, filterable by monster, quest, stars, weapon, hunter. | FR-3.1 — ハントごとのローリングDPSとクリアタイム。モンスター・クエスト・難易度・武器・ハンターで絞り込み。 |  |
| `tab.growth` | Growth | 成長 |  |
| `tab.growth.blurb` | Instance-weighted DPS change with per-group trends (median, best, slope, clear time). Single hunter drill-down, multi-hunter scope, monster/star/weapon/variant filters. | インスタンス加重のDPS推移とグループ別トレンド（中央値・最高値・傾き・クリアタイム）。1人のハンターの詳細から複数ハンターの比較まで、モンスター・難易度・武器・ビルドで絞り込み可能。 |  |
| `tab.weapons` | Weapons | 武器 |  |
| `tab.weapons.blurb` | FR-3.2 — avg/peak DPS, hunt count and clear rate by weapon type. | FR-3.2 — 武器種別の平均・最大DPS、ハント数、クリア率。 |  |
| `tab.highlights` | Highlights | ハイライト |  |
| `tab.highlights.blurb` | Quest-end hunter highlights (awards) and average damage share, per monster/weapon/hunter. REFramework hunts only. | クエスト終了時のハイライト（褒賞）と平均ダメージシェア。モンスター・武器・ハンター別。REFramework のハントのみ。 |  |
| `tab.curves` | Damage curves | ダメージカーブ |  |
| `tab.curves.blurb` | FR-3.3 — per-hunt cumulative damage overlay for all party members, monster HP curve, enrage markers. | FR-3.3 — ハントごとのパーティ全員の累積ダメージ重ね表示、モンスターHPカーブ、怒り状態のマーカー。 |  |
| `tab.hunts` | Hunts | ハント |  |
| `tab.hunts.blurb` | Every run, latest first — click a row for party damage, DPS, hunter highlights and the damage curve. | すべてのハントを新しい順に表示。行をクリックするとパーティのダメージ、DPS、ハイライト、ダメージカーブが見られます。 |  |
| `tab.survival` | Survival | 生存 |  |
| `tab.survival.blurb` | Per-hunter HP and DPS over time with time-in-danger summary. Requires HuntDumper 0.11+. | ハンター別のHPとDPSの推移、危険時間の集計。HuntDumper 0.11 以降が必要です。 |  |
| `tab.leaderboard` | Leaderboard | ランキング |  |
| `tab.leaderboard.blurb` | Best players by DPS over cleared hunts — filterable by monster, stars, weapon and min hunts. | クリア済みハントのDPSでハンターをランキング。モンスター・難易度・武器・最低ハント数で絞り込み。 |  |
| `tab.highscores` | High Scores | ハイスコア |  |
| `tab.highscores.blurb` | One row per cleared hunt, ranked by top DPS or fastest clear. Scoped to the hunters bar above; filterable by monster, weapon and stars. | クリアしたハントを1行ずつ、最高DPSまたは最速クリアで並べます。上のハンター選択が対象。モンスター・武器・難易度で絞り込み。 |  |
| `tab.compare` | Compare | 比較 |  |
| `tab.compare.blurb` | Your scoped hunters vs the whole party, hunt by hunt. Star yourself in the hunters bar above. | 選択中のハンターとパーティ全体をハントごとに比較します。上のハンターバーで自分に★を付けてください。 |  |
| `tab.activity` | Activity | アクティビティ |  |
| `tab.activity.blurb` | Hunt volume, clear rate and damage output day by day. | ハント数、クリア率、ダメージ量を日ごとに表示。 |  |
| `tab.synergy` | Synergy | シナジー |  |
| `tab.synergy.blurb` | FR-3.4 — clear time and damage share by teammate pairing (supporters excluded). | FR-3.4 — 一緒に狩る組み合わせごとのクリアタイムとダメージシェア（サポート勢を除く）。 |  |
| `tab.buffs` | Buffs | バフ |  |
| `tab.buffs.blurb` | Consumable, skill, song and debuff uptime for the local player, plus the monster's enrage and ailment timeline. Recorded by the HunterPie Analytics companion. | ローカルプレイヤーのアイテム・スキル・旋律・デバフの維持時間と、モンスターの怒り・状態異常のタイムライン。HunterPie Analytics コンパニオンが記録します。 |  |

## Hunter scope bar, party filter, weapon/build pickers
<sub>locales/*/scope.json · 28 strings</sub>

| key | English | 日本語 | source |
| --- | --- | --- | --- |
| `scope.hunters` | Hunters: | ハンター: |  |
| `scope.allHunters` | all hunters | 全ハンター |  |
| `scope.removeFromScope` | remove from scope | スコープから外す |  |
| `scope.addHunters` | + hunters | + ハンター |  |
| `scope.searchHunters` | Search hunters… | ハンターを検索… |  |
| `scope.starred` | Starred | スター付き |  |
| `scope.noHunters` | no hunters yet | ハンターがまだいません |  |
| `scope.clear` | clear | クリア |  |
| `scope.party` | Party: | パーティ: |  |
| `scope.partyFilter` | Party size filter | パーティ人数で絞り込み |  |
| `scope.weapon` | Weapon | 武器 |  |
| `scope.allWeapons` | All weapons | すべての武器 |  |
| `scope.weaponName` | Weapon name | 武器名 |  |
| `scope.nameWeapons` | Name your weapons | 武器に名前を付ける |  |
| `scope.unpin` | unpin | ピンを解除 |  |
| `scope.pin` | pin (star) | ピン留め（スター） |  |
| `scope.hunts.one` | {n} hunt | {n} ハント |  |
| `scope.hunts.other` | {n} hunts | {n} ハント |  |
| `scope.nameWeaponsHint` | Each distinct weapon you have used is listed once — give it a name and every hunt with those stats resolves to it. | 使用した武器ごとに1件ずつ表示されます。名前を付けると、同じ性能のハントがすべてその武器としてまとまります。 |  |
| `scope.variantPlaceholder` | e.g. "Artian Horn III" | 例: 「Artian Horn III」 |  |
| `scope.rename` | Rename | 名前を変更 |  |
| `scope.nameIt` | Name it | 名前を付ける |  |
| `scope.unknownHunts.one` | + {n} hunt from before weapon tracking (shown as Unknown). | + 武器記録前の {n} ハント（不明として表示）。 |  |
| `scope.unknownHunts.other` | + {n} hunts from before weapon tracking (shown as Unknown). | + 武器記録前の {n} ハント（不明として表示）。 |  |
| `scope.search.placeholder` | All — type to search | すべて — 入力して検索 |  |
| `scope.search.clear` | Clear {label} | {label} をクリア |  |
| `scope.search.matches` | {n} matches — keep typing to narrow | {n} 件一致 — 入力を続けて絞り込み |  |
| `scope.search.noMatches` | no matches | 一致なし |  |

## Settings dialog, update pill, mod pill, What's new
<sub>locales/*/settings.json · 84 strings</sub>

| key | English | 日本語 | source |
| --- | --- | --- | --- |
| `changelog.1.2.4.0` | Hunts for a monster that only invaded the quest — a Guardian Rathalos in an Arkveld quest, for example — are now hidden automatically, exactly like pressing Ignore. | クエストに乱入しただけのモンスター（例: アルクヴェルドのクエストに乱入した護竜リオレウス）とのハントは、「除外」を押したときとまったく同じように自動で非表示になります。 |  |
| `changelog.1.2.4.1` | Settings → Data → “Only quest objectives” turns it on or off. Older hunts are re-read from your export files, so the filter covers past quests too. | 設定 → データ →「クエスト目標のみ」でオン/オフできます。古いハントもエクスポートファイルから再読み込みされるため、過去のクエストにもフィルターが適用されます。 |  |
| `changelog.1.2.4.2` | Ignores you made yourself are always kept. Turning the filter off restores only the hunts it hid. No mod update needed. | 自分で設定した除外は常に保持されます。フィルターをオフにすると、フィルターが非表示にしたハントだけが復元されます。MOD の更新は不要です。 |  |
| `changelog.1.2.4.3` | Hunts → All hunts now has Delete as well as Ignore: Delete removes a hunt from every stat and from the list for good (a re-import won't bring it back), and “Show deleted” lets you restore one. | ハント → すべてのハントに「除外」に加えて「削除」が追加されました。削除すると、そのハントはすべての統計と一覧から完全に取り除かれ（再インポートでも戻りません）、「削除済みを表示」で復元できます。 |  |
| `changelog.1.2.4.title` | Only quest objectives | クエスト目標のみ |  |
| `changelog.1.2.5.0` | The “What's new” note now stays closed after you close it. It used to come back on every launch because the desktop app picked a new local port each time, which reset the browser storage that remembered it. | 「新着情報」は閉じたあと再表示されなくなりました。以前は起動のたびにデスクトップアプリが新しいローカルポートを選び、表示状態を記憶していたブラウザーストレージがリセットされていたため、毎回表示されていました。 |  |
| `changelog.1.2.5.1` | The app now keeps a stable local port, so your last tab, hunter scope, filters and party size are remembered across launches too. | アプリが安定したローカルポートを使うようになったため、最後に開いたタブ、ハンターのスコープ、フィルター、パーティ人数も起動をまたいで記憶されます。 |  |
| `changelog.1.2.5.title` | Fixes | 修正 |  |
| `changelog.1.2.6.0` | Each hunter’s rank is now shown next to their name in a hunt’s party cards and in the Hunters tooltip — read from the HunterPie companion’s party export. | 各ハンターのランクが、ハントのパーティカードとハンターのツールチップで名前の横に表示されるようになりました（HunterPie コンパニオンのパーティエクスポートから読み取ります）。 |  |
| `changelog.1.2.6.1` | Party HP curves are now keyed by the game’s network member index, so a hunter’s near-death curve can no longer be assigned to another player. | パーティHPカーブはゲームのネットワークメンバーインデックスをキーにするようになったため、あるハンターの瀕死カーブが別のプレイヤーに割り当てられることはなくなりました。 |  |
| `changelog.1.2.6.2` | A companion restarted mid-hunt is now merged back into the same hunt instead of creating a duplicate with no HP. | ハント中に再起動したコンパニオンは、HP のない重複ハントを作らず、同じハントに統合されるようになりました。 |  |
| `changelog.1.2.6.3` | Bundles HuntDumper 0.12.7. If the mod pill asks you to reinstall, update the REFramework mod to match. | HuntDumper 0.12.7 を同梱しています。MOD ピルで再インストールを求められた場合は、REFramework MOD を更新してください。 |  |
| `changelog.1.2.6.title` | Hunter rank & HP fixes | ハンターランクとHPの修正 |  |
| `changelog.1.3.0.0` | The dashboard now speaks Japanese. Switch the language in Settings → Display; it defaults to your browser's language and the choice is remembered. | ダッシュボードが日本語に対応しました。設定 → 表示 から言語を切り替えられます。初期値はブラウザの言語で、選択は保存されます。 |  |
| `changelog.1.3.0.1` | Monster and skill names come from the game's own Japanese text, so the app uses the same words as the quest results screen. Quest award names are a literal first pass, pending native review. | モンスター名とスキル名はゲーム本体の日本語テキストを使用しているため、クエスト結果画面と同じ表記になります。クエスト褒賞名は直訳による初版です（ネイティブレビュー待ち）。 |  |
| `changelog.1.3.0.2` | Numbers, dates and durations follow the selected language, and charts/tables re-render on the fly when you switch. | 数値・日付・時間の表記も選択した言語に合わせて切り替わり、切り替えた瞬間にグラフや表も更新されます。 |  |
| `changelog.1.3.0.title` | Japanese UI | 日本語UI |  |
| `settings.checkUpdates` | Check for updates | アップデートを確認 |  |
| `settings.checkUpdatesHint` | Asks GitHub for the latest release so the app can update itself in place. Off = no network requests at all. | GitHub に最新リリースを問い合わせ、アプリをその場で更新できるようにします。オフにするとネットワーク通信は一切行いません。 |  |
| `settings.data` | Data | データ |  |
| `settings.display` | Display | 表示 |  |
| `settings.dpsEngagementBody` | Your active fighting time. Late joiners are divided by their own time in the fight. | 実際に戦っていた時間で割ります。途中参加のハンターは、そのハンター自身の戦闘時間で割られます。 |  |
| `settings.dpsEngagementTitle` | First → last hit | 初撃 → 最後の攻撃 |  |
| `settings.dpsQuestBody` | Freezes when the monster goes down (quest end if nothing did), matching the in-game meter. | モンスターが倒れた時点で確定します（何も倒れていなければクエスト終了時）。ゲーム内メーターと同じ計算です。 |  |
| `settings.dpsQuestTitle` | First hit → kill | 初撃 → 討伐 |  |
| `settings.dpsWindow` | DPS window | DPS 計測範囲 |  |
| `settings.exports` | Hunt exports folders | ハントエクスポートフォルダー |  |
| `settings.exportsActive` | Active sources: {kinds}. | 有効な取得元: {kinds}。 |  |
| `settings.exportsEnvSuffix` |  is set and overrides this list. |  が設定されているため、この一覧は上書きされます。 |  |
| `settings.exportsFolder` | Hunt exports folder | ハントエクスポートフォルダー |  |
| `settings.exportsHintLead` | Extra folders to scan, e.g. a Mod Organizer 2 instance: | スキャンする追加フォルダー（Mod Organizer 2 のインスタンスなど）: |  |
| `settings.exportsHintTail` | . | 。 |  |
| `settings.exportsMissing` | Not found yet: {dirs} | まだ見つかりません: {dirs} |  |
| `settings.exportsRemove` | Remove {dir} | {dir} を削除 |  |
| `settings.includeFailed` | Include failed hunts | 失敗したハントを含める |  |
| `settings.includeFailedHint` | Counts carted-out quests in performance stats. Clear rates always count failures, and hunts that never engaged a target aren't recorded at all. | クエスト失敗（力尽きて戻された）ハントも成績に含めます。クリア率は常に失敗を数え、ターゲットと交戦しなかったハントは記録されません。 |  |
| `settings.language` | Language | 言語 |  |
| `settings.mod.bodyBefore` | This app ships HuntDumper | このアプリの HuntDumper は |  |
| `settings.mod.bodyEnd` | . |  です。 |  |
| `settings.mod.bodyMiddle` | , but the newest mod dump came from |  ですが、最新の MOD ダンプは |  |
| `settings.mod.copyAfter` | from the app's install folder to: | を次の場所にコピーしてください: |  |
| `settings.mod.copyBefore` | Copy | アプリのインストールフォルダーから |  |
| `settings.mod.download` | Download the latest mod | 最新の MOD をダウンロード |  |
| `settings.mod.heading` | Update the REFramework mod | REFramework MOD を更新 |  |
| `settings.mod.modalLabel` | Update the REFramework mod | REFramework MOD を更新 |  |
| `settings.mod.overwrite` | Overwrite the old file, then restart the game. Party HP (Survival) and time-up failure detection need the newer mod. | 古いファイルを上書きしてから、ゲームを再起動してください。パーティHP（Survival）とタイムアップ失敗の検出には新しい MOD が必要です。 |  |
| `settings.mod.pill` | Mod v{installed} → reinstall | MOD v{installed} → 再インストール |  |
| `settings.mod.title` | The app ships HuntDumper v{expected}; your newest mod dump came from v{installed}. | このアプリには HuntDumper v{expected} が同梱されていますが、最新の MOD ダンプは v{installed} から出力されています。 |  |
| `settings.mod.toast` | App updated — reinstall HuntDumper v{version} to enable party HP and quest results. | アプリが更新されました — パーティHPとクエスト結果を有効にするには HuntDumper v{version} を再インストールしてください。 |  |
| `settings.questTargetsOnly` | Only quest objectives | クエスト目標のみ |  |
| `settings.questTargetsOnlyHint` | Hides hunts whose monster was not the quest objective — an invading Guardian Rathalos, for example — exactly like pressing Ignore. Applies to older hunts too when the companion recorded which monsters were targets; turning it off restores them. Your own ignores are always kept. | クエストの目標でないモンスターとのハント（例: 乱入した護竜リオレウス）を、「除外」を押したときと同じように非表示にします。コンパニオンがターゲットを記録している古いハントにも適用され、オフにすると元に戻ります。自分で設定した除外は常に保持されます。 |  |
| `settings.source.hunterpie` | HunterPie | HunterPie |  |
| `settings.source.reframework` | REFramework | REFramework |  |
| `settings.theme` | Theme | テーマ |  |
| `settings.themeDark` | Dark | ダーク |  |
| `settings.themeLight` | Light | ライト |  |
| `settings.title` | Settings | 設定 |  |
| `settings.toast.dpsEngagement` | DPS now divides by first → last hit | DPS は初撃 → 最後の攻撃で割るようになりました |  |
| `settings.toast.dpsQuest` | DPS now divides by own first hit → quest end | DPS は自身の初撃 → クエスト終了で割るようになりました |  |
| `settings.toast.filterOff` | Quest-objective filter off — auto-hidden hunts restored | クエスト目標フィルターをオフ — 自動非表示だったハントを復元しました |  |
| `settings.toast.filterOn` | Quest-objective filter on | クエスト目標フィルターをオンにしました |  |
| `settings.toast.filterPartial` | Filter applied to known hunts; older hunts need Full recheck (another import may be running) | 既知のハントにはフィルターを適用しました。古いハントには「完全再確認」が必要です（別のインポートが実行中の可能性があります）。 |  |
| `settings.toast.huntsHidden.one` | Filter on — {n} hunt hidden | フィルターオン — ハント {n} 件を非表示にしました |  |
| `settings.toast.huntsHidden.other` | Filter on — {n} hunts hidden | フィルターオン — ハント {n} 件を非表示にしました |  |
| `settings.toast.rechecked` | Quest-objective filter applied — {n} export(s) rechecked | クエスト目標フィルターを適用 — エクスポート {n} 件を再確認しました |  |
| `settings.toast.rechecking` | Filter on — rechecking exports to cover {n} older hunt(s)… | フィルターオン — 古いハント {n} 件を対象にするためエクスポートを再確認中… |  |
| `settings.toast.saveFailed` | Could not save settings | 設定を保存できませんでした |  |
| `settings.toast.saved` | Hunt exports folder saved | ハントエクスポートフォルダーを保存しました |  |
| `settings.toast.savedMissing` | Saved. That folder doesn't exist yet — it will be scanned once it does. | 保存しました。このフォルダーはまだ存在しません — 作成され次第スキャンされます。 |  |
| `settings.update.availableDownload` | ↓ v{version} available | ↓ v{version} が利用可能 |  |
| `settings.update.availableInstall` | ↑ v{version} available | ↑ v{version} が利用可能 |  |
| `settings.update.downloading` | Downloading v{version}… | v{version} をダウンロード中… |  |
| `settings.update.downloadingSize` | Downloading v{version} (~{mb} MB)… | v{version} をダウンロード中（約 {mb} MB）… |  |
| `settings.update.failed` | Update failed | 更新に失敗しました |  |
| `settings.update.installing` | Installing — the app will close and reopen updated. | インストール中 — アプリは終了し、更新後に再起動します。 |  |
| `settings.update.openFailed` | Could not open the download | ダウンロードを開けませんでした |  |
| `settings.update.opening` | Opening the v{version} download in your browser. | v{version} のダウンロードをブラウザーで開いています。 |  |
| `settings.update.titleDownload` | Download v{version} in your browser | v{version} をブラウザーでダウンロード |  |
| `settings.update.titleInstall` | Update to v{version} | v{version} に更新 |  |
| `settings.update.updating` | Updating… | 更新中… |  |
| `settings.versionLabel` | you have | 現在のバージョン: |  |
| `settings.whatsNew` | What's new | 新着情報 |  |
| `settings.whatsNew.heading` | What's new in v{version} | v{version} の新着情報 |  |
| `settings.whatsNew.releaseNotes` | Full release notes on GitHub | GitHub でリリースノート全文を見る |  |

## Tables, filters, empty states, dialogs, toasts, charts, hunt manager
<sub>locales/*/table.json · 61 strings</sub>

| key | English | 日本語 | source |
| --- | --- | --- | --- |
| `table.empty.none` | No {what} yet. | {what}はまだありません。 |  |
| `table.empty.scope` | No hunts for {names} match these filters. | {names} のハントはこのフィルタに一致しません。 |  |
| `table.empty.clearScope` | Clear hunter scope | ハンター範囲を解除 |  |
| `table.sort.title` | click to sort | クリックで並べ替え |  |
| `table.pager.prev` | Prev | 前へ |  |
| `table.pager.next` | Next | 次へ |  |
| `table.pager.rows` | Rows | 表示件数 |  |
| `table.pager.status` | Page {page} of {pages} · {rows} rows | {pages} ページ中 {page} ページ · {rows} 行 |  |
| `table.toast.dismiss` | Dismiss | 閉じる |  |
| `table.filter.monster` | Monster | モンスター |  |
| `table.filter.stars` | Stars | ★の数 |  |
| `table.filter.weapon` | Weapon | 武器 |  |
| `table.filter.hunter` | Hunter | ハンター |  |
| `table.filter.highlights` | Highlights | ハイライト |  |
| `table.chart.enraged` | {monster} enraged | {monster} が怒り状態 |  |
| `table.card.hunterRank` | Hunter Rank {rank} | ハンターランク {rank} |  |
| `table.import.cancelled.one` | Import cancelled — {count} new hunt kept | インポートを中止しました — 新規ハント {count} 件を保存 |  |
| `table.import.cancelled.other` | Import cancelled — {count} new hunts kept | インポートを中止しました — 新規ハント {count} 件を保存 |  |
| `table.import.failed` | Import failed: {error} | インポートに失敗しました: {error} |  |
| `table.import.unknownError` | unknown error | 不明なエラー |  |
| `table.import.failedFiles.one` | {count} file failed (first: {file}) — {imported} new | {count} 件のファイルで失敗しました（先頭: {file}）— 新規 {imported} 件 |  |
| `table.import.failedFiles.other` | {count} files failed (first: {file}) — {imported} new | {count} 件のファイルで失敗しました（先頭: {file}）— 新規 {imported} 件 |  |
| `table.import.upToDate` | Up to date — {scanned} files ({skipped} skipped), nothing new | 最新の状態です — {scanned} ファイル（{skipped} 件スキップ）、新規なし |  |
| `table.import.importedNotes.one` | Imported {count} new hunt · {notes} import notes | 新規ハント {count} 件をインポート · 注記 {notes} 件 |  |
| `table.import.importedNotes.other` | Imported {count} new hunts · {notes} import notes | 新規ハント {count} 件をインポート · 注記 {notes} 件 |  |
| `table.import.imported.one` | Imported {count} new hunt | 新規ハント {count} 件をインポートしました |  |
| `table.import.imported.other` | Imported {count} new hunts | 新規ハント {count} 件をインポートしました |  |
| `table.import.alreadyRunning` | An import is already running | インポートはすでに実行中です |  |
| `table.import.failedDefault` | Import failed | インポートに失敗しました |  |
| `table.import.button` | Import hunts | ハントをインポート |  |
| `table.import.busy` | Importing… | インポート中… |  |
| `table.import.fullRecheck` | Full recheck | 全ファイル再確認 |  |
| `table.import.fullRecheckTitle` | Ignore the skip manifest and recheck every file (e.g. after deleting hunts) | スキップ記録を無視して全ファイルを再確認します（ハント削除後など） |  |
| `table.import.cancelTitle` | Stop after the current file | 現在のファイルを処理した後に停止 |  |
| `table.import.progress` | Import progress | インポートの進捗 |  |
| `table.import.progressDetail` | {imported} new · {duplicates} dupes | 新規 {imported} · 重複 {duplicates} |  |
| `table.hunts.open` | Hunts | ハント |  |
| `table.hunts.manageLabel` | Manage hunts | ハントの管理 |  |
| `table.hunts.title` | All hunts | すべてのハント |  |
| `table.hunts.search` | Search by monster, #id, or date… | モンスター・#ID・日付で検索… |  |
| `table.hunts.showDeleted` | Show deleted | 削除済みを表示 |  |
| `table.hunts.confirmLabel` | Confirm delete | 削除の確認 |  |
| `table.hunts.confirmBefore` | Delete hunt | ハント |  |
| `table.hunts.confirmAfter` | ? It is removed from every stat and from this list, and a re-import won't bring it back. | を削除しますか？すべての統計とこの一覧から削除され、再インポートしても元に戻りません。 |  |
| `table.hunts.toggleFailed` | Toggle failed | 切り替えに失敗しました |  |
| `table.hunts.deleteFailed` | Delete failed | 削除に失敗しました |  |
| `table.hunts.restoreFailed` | Restore failed | 復元に失敗しました |  |
| `table.hunts.deletedToast` | Hunt #{id} deleted. | ハント #{id} を削除しました。 |  |
| `table.hunts.restoredToast` | Hunt #{id} restored. | ハント #{id} を復元しました。 |  |
| `table.hunts.players` | {count}p | {count}人 |  |
| `table.hunts.cleared` | cleared | クリア |  |
| `table.hunts.failed` | failed | 失敗 |  |
| `table.hunts.deleted` | deleted | 削除済み |  |
| `table.hunts.restoreTitle` | Restore deleted hunt #{id} | 削除済みハント #{id} を復元 |  |
| `table.hunts.restore` | Restore | 復元 |  |
| `table.hunts.restoreIgnoredTitle` | Restore hunt #{id} to stats | ハント #{id} を統計に戻す |  |
| `table.hunts.ignoreTitle` | Ignore hunt #{id} in stats | ハント #{id} を統計から除外 |  |
| `table.hunts.ignore` | Ignore | 除外 |  |
| `table.hunts.delete` | Delete | 削除 |  |
| `table.hunts.deleteTitle` | Delete hunt #{id} permanently | ハント #{id} を完全に削除 |  |
| `table.hunts.noMatch` | No hunts match. | 一致するハントはありません。 |  |

## Progress tab
<sub>locales/*/views.progress.json · 31 strings</sub>

| key | English | 日本語 | source |
| --- | --- | --- | --- |
| `progress.metric.dps.label` | DPS | DPS |  |
| `progress.metric.dps.title` | DPS per hunt | ハントごとのDPS |  |
| `progress.metric.dps.axis` | DPS | DPS |  |
| `progress.metric.dps.note` | Raw damage per second over your active window — sensitive to which monster you fought and how long the fight lasted. | アクティブ時間あたりの素のダメージ毎秒。相手のモンスターや戦闘時間の影響を受けます。 |  |
| `progress.metric.index.label` | vs usual | 通常比 |  |
| `progress.metric.index.title` | DPS vs your usual on that monster | そのモンスターでの通常DPS比 |  |
| `progress.metric.index.axis` | % of usual | 通常比 (%) |  |
| `progress.metric.index.note` | 100% = your median DPS on the same monster across these hunts, so switching to a harder or easier fight stops reading as a slump or a spike. | 100% = このハント群における同じモンスターでの自分のDPS中央値。難しい相手・簡単な相手に切り替わっても、不調や急上昇として見えなくなります。 |  |
| `progress.metric.share.label` | Damage share | ダメージシェア |  |
| `progress.metric.share.title` | Damage share per hunt | ハントごとのダメージシェア |  |
| `progress.metric.share.axis` | % of party | パーティ比 (%) |  |
| `progress.metric.share.note` | Your part of the party's total damage — roughly flat when the whole party (or the monster's HP) changes, so it tracks your relative contribution. | パーティ総ダメージに占める自分の割合。パーティ全体やモンスターHPが変わってもほぼ一定なので、相対的な貢献度を追えます。 |  |
| `progress.metric.clear.label` | Clear time | クリアタイム |  |
| `progress.metric.clear.title` | Clear time per hunt | ハントごとのクリアタイム |  |
| `progress.metric.clear.axis` | clear time | クリアタイム |  |
| `progress.metric.clear.note` | Finish time per quest (m:ss) — lower is better; mixes in damage, routing and monster uptime. | クエストごとの討伐時間（m:ss）。短いほど良く、ダメージ・動き・モンスターの滞在時間が混ざります。 |  |
| `progress.filter.quest` | Quest | クエスト |  |
| `progress.filter.rollingWindow` | Rolling window | ローリング期間 |  |
| `progress.filter.hunts` | Hunts | ハント数 |  |
| `progress.filter.last50` | Last 50 | 直近50件 |  |
| `progress.filter.last100` | Last 100 | 直近100件 |  |
| `progress.filter.last200` | Last 200 | 直近200件 |  |
| `progress.empty.scope` | They aren't in these hunts — pick something they joined. | このハントには参加していません — 参加したハントを選んでください。 |  |
| `progress.empty.none` | hunts match these filters | 条件に一致するハント |  |
| `progress.empty.import` | Import one with | 取り込み例: |  |
| `progress.measure` | Measure | 指標 |  |
| `progress.measureAria` | Progress measure | 進捗の指標 |  |
| `progress.heading` | {title} + {window}-hunt rolling average | {title} + {window}ハントの移動平均 |  |
| `progress.series.avg` | rolling avg | 移動平均 |  |
| `progress.series.clearTime` | clear time | クリアタイム |  |
| `progress.axis.usual` | usual | 通常 |  |

## Growth tab
<sub>locales/*/views.growth.json · 44 strings</sub>

| key | English | 日本語 | source |
| --- | --- | --- | --- |
| `growth.measureAria` | Growth measure | 成長の指標 |  |
| `growth.mode.firstLast.label` | First → last | 初回 → 最新 |  |
| `growth.mode.firstLast.note` | Compares the first and the newest hunt of each group — what the tab always showed, and the most sensitive to one lucky or one bad hunt. | 各グループの最初と最新のハントを比較します。このタブが従来から表示していた方法で、1回の好調・不調の影響を最も受けやすくなります。 |  |
| `growth.mode.edgeMedians.label` | First 3 vs last 3 | 最初の3件 vs 最後の3件 |  |
| `growth.mode.edgeMedians.note` | Compares the first and last hunts of each group by median (up to three each, never the same hunt twice), so one outlier at either end is far less decisive than in first → last. | 各グループの最初と最後のハントを中央値で比較します（それぞれ最大3件、同じハントは二度使いません）。両端の外れ値1件の影響は、初回 → 最新よりもはるかに小さくなります。 |  |
| `growth.mode.trend.label` | Trend fit | トレンド近似 |  |
| `growth.mode.trend.note` | Fits a straight line through every hunt in the group and reports the change across its span — uses all the evidence instead of two endpoints. | グループ内の全ハントに直線を当てはめ、その期間全体の変化を報告します。2つの端点ではなく、すべてのデータを使います。 |  |
| `growth.sparkline.up` | DPS trend up | DPSトレンド（上昇） |  |
| `growth.sparkline.down` | DPS trend down | DPSトレンド（下降） |  |
| `growth.filter.minHunts` | Min hunts | 最低ハント数 |  |
| `growth.filter.top` | Top | 上位 |  |
| `growth.loading` | Loading growth analytics… | 成長分析を読み込み中… |  |
| `growth.empty.player` | No monster/star groups with at least {min} hunts found for this hunter with these filters. | このハンターには、現在の条件で{min}ハント以上のモンスター・難易度グループが見つかりません。 |  |
| `growth.empty.scope` | No multi-hunt monster/star groups for these hunters with these filters. | 現在の条件では、対象ハンターに複数ハントのモンスター・難易度グループがありません。 |  |
| `growth.empty.none` | hunter improvement data | ハンターの成長データ |  |
| `growth.empty.hint` | No multi-instance monster/star hunt records found across players. | プレイヤー全体で、複数回のモンスター・難易度ハント記録が見つかりません。 |  |
| `growth.player.heading` | {name}'s Growth & Improvement | {name}の成長と改善 |  |
| `growth.summary.one` | Instance-weighted growth across {n} monster & star group (≥{min} hunts each). | {n}グループのモンスター・難易度（各{min}ハント以上）にわたるインスタンス加重の成長。 |  |
| `growth.summary.other` | Instance-weighted growth across {n} monster & star groups (≥{min} hunts each). | {n}グループのモンスター・難易度（各{min}ハント以上）にわたるインスタンス加重の成長。 |  |
| `growth.weighted` | Weighted growth | 加重成長率 |  |
| `growth.groups.heading` | Monster & Star Groups (≥{min} hunts) | モンスター・難易度グループ（{min}ハント以上） |  |
| `growth.group.first3` | First 3: | 最初の3件: |  |
| `growth.group.last3` | Last 3: | 最後の3件: |  |
| `growth.group.fit` | Fit: | 近似: |  |
| `growth.group.first` | First: | 初回: |  |
| `growth.group.latest` | Latest: | 最新: |  |
| `growth.group.perHuntPct` | %/hunt | %/ハント |  |
| `growth.group.perHunt` | /hunt | /ハント |  |
| `growth.group.median` | Median: | 中央値: |  |
| `growth.group.best` | Best: | 最高: |  |
| `growth.group.slope` | Slope: | 傾き: |  |
| `growth.group.clear` | Clear: | クリア: |  |
| `growth.group.faster` |  ({pct}% faster) | （{pct}%高速化） |  |
| `growth.group.huntTitle` | Hunt #{id} ({date}): {dps} DPS | ハント #{id}（{date}）: {dps} DPS |  |
| `growth.group.huntTitleClear` | , {time} | 、{time} |  |
| `growth.group.firstTag` |  ·1st | ・初回 |  |
| `growth.group.newTag` |  ·new | ・最新 |  |
| `growth.top.heading` | Top Hunters by Growth | 成長率の高いハンター |  |
| `growth.top.blurb` | Instance-weighted growth across monster & star groups with ≥{min} hunts. | モンスター・難易度グループ（{min}ハント以上）にわたるインスタンス加重の成長。 |  |
| `growth.top.scoped` | Scoped to {n} hunters —  | 対象ハンター: {n}人 —  |  |
| `growth.top.select` | Select a hunter for the full breakdown. | ハンターを選ぶと詳細を表示します。 |  |
| `growth.top.view` | View {name} growth | {name}の成長を見る |  |
| `growth.top.groups.one` | {n} monster/star group (≥{min} hunts) | {n}グループのモンスター・難易度（{min}ハント以上） |  |
| `growth.top.groups.other` | {n} monster/star groups (≥{min} hunts) | {n}グループのモンスター・難易度（{min}ハント以上） |  |

## Weapons tab
<sub>locales/*/views.weapons.json · 12 strings</sub>

| key | English | 日本語 | source |
| --- | --- | --- | --- |
| `weapons.column.weapon` | Weapon | 武器 |  |
| `weapons.column.hunts` | Hunts | ハント数 |  |
| `weapons.column.avgDps` | Avg DPS | 平均DPS |  |
| `weapons.column.peak` | Peak hit* | ピークヒット* |  |
| `weapons.column.clearPct` | Clear % | クリア率 |  |
| `weapons.chart.heading` | Average DPS by weapon | 武器種別の平均DPS |  |
| `weapons.chart.xAxis` | average DPS | 平均DPS |  |
| `weapons.chart.series` | avg DPS | 平均DPS |  |
| `weapons.table.heading` | Weapon performance matrix (click a header to sort) | 武器パフォーマンス一覧（ヘッダーをクリックで並べ替え） |  |
| `weapons.table.note` | * Peak hit = biggest single damage frame, not sustained DPS. | * ピークヒット = 単発の最大ダメージ（持続DPSではありません）。 |  |
| `weapons.empty.none` | weapon data for these filters | 条件に一致する武器データ |  |
| `weapons.empty.hint` | Try a different filter combination. | 別のフィルタ条件を試してください。 |  |

## Highlights tab
<sub>locales/*/views.highlights.json · 16 strings</sub>

| key | English | 日本語 | source |
| --- | --- | --- | --- |
| `highlights.player` | Player | ハンター |  |
| `highlights.total` | Total | 合計 |  |
| `highlights.best` | Best (single hunt) | ベスト（単一ハント） |  |
| `highlights.hunts` | Hunts | ハント数 |  |
| `highlights.avgShare` | Avg damage share | 平均ダメージシェア |  |
| `highlights.leaderboard` | Highlight leaderboard | 褒賞ランキング |  |
| `highlights.award` | Award | 褒賞 |  |
| `highlights.shareTitle` | Average damage share | 平均ダメージシェア |  |
| `highlights.all` | All highlights | すべての褒賞 |  |
| `highlights.topHunter` | Top hunter | トップハンター |  |
| `highlights.noAwards` | No awards recorded for these filters. | この条件の褒賞記録はありません。 |  |
| `highlights.noneSelected` | No highlights selected — pick some under “Highlights”. | ハイライトが未選択です。「ハイライト」で選択してください。 |  |
| `highlights.noDamage` | No damage data for these filters. | この条件のダメージデータはありません。 |  |
| `highlights.tableNone` | No highlights selected. | ハイライトが未選択です。 |  |
| `highlights.empty.what` | hunter highlights for these filters | この条件のハンター褒賞 |  |
| `highlights.empty.note` | Awards come from the REFramework mod. HunterPie-fork hunts have no awards. | 褒賞は REFramework MOD から取得します。HunterPie 解析版のハントには褒賞がありません。 |  |

## Damage curves tab
<sub>locales/*/views.curves.json · 26 strings</sub>

| key | English | 日本語 | source |
| --- | --- | --- | --- |
| `curves.hunt` | Hunt | ハント |  |
| `curves.monsterPlaceholder` | All monsters — type to search | すべてのモンスター — 入力して検索 |  |
| `curves.showHp` | Monster HP | モンスターHP |  |
| `curves.metric` | Metric | 指標 |  |
| `curves.metric.damage` | Cumulative damage | 累積ダメージ |  |
| `curves.metric.dps` | DPS (5s rolling avg) | DPS（5秒移動平均） |  |
| `curves.metric.burst` | Instantaneous DPS (5s window) | 瞬間DPS（5秒窓） |  |
| `curves.metric.burst1` | Instantaneous DPS (1s window) | 瞬間DPS（1秒窓） |  |
| `curves.hint.zoom` | Drag chart to zoom · click a hunter to hide or show it | ドラッグで拡大 · ハンターをクリックで表示/非表示 |  |
| `curves.showAll` | Show all hunters | 全ハンターを表示 |  |
| `curves.showAll.title` | Show every hunter again | すべてのハンターを再表示 |  |
| `curves.resetZoom` | Reset zoom | 拡大をリセット |  |
| `curves.resetZoom.title` | Restore the full quest timeline | クエスト全体のタイムラインに戻す |  |
| `curves.quest` | quest #{id} | クエスト #{id} |  |
| `curves.clearedIn` | cleared in {time} | {time} でクリア |  |
| `curves.axis.time` | time since quest start | クエスト開始からの経過時間 |  |
| `curves.axis.damage` | cumulative damage | 累積ダメージ |  |
| `curves.axis.dps` | DPS (5s window) | DPS（5秒窓） |  |
| `curves.axis.dps1` | DPS (1s window) | DPS（1秒窓） |  |
| `curves.axis.hp` | monster HP | モンスターHP |  |
| `curves.enragedSpans` | enraged {spans} | 怒り状態: {spans} |  |
| `curves.legend.label` | Chart visibility | グラフの表示切替 |  |
| `curves.legend.show` | Show {name} | {name} を表示 |  |
| `curves.legend.hide` | Hide {name} | {name} を非表示 |  |
| `curves.empty.what` | hunts | ハント |  |
| `curves.empty.import` | Import one with | 次のコマンドでインポート: |  |

## Hunts tab
<sub>locales/*/views.hunts.json · 36 strings</sub>

| key | English | 日本語 | source |
| --- | --- | --- | --- |
| `hunts.col.id` | Hunt | ハント |  |
| `hunts.col.date` | Date | 日付 |  |
| `hunts.col.quest` | Quest | クエスト |  |
| `hunts.col.clear` | Clear | クリア |  |
| `hunts.col.hunters` | Hunters | ハンター |  |
| `hunts.col.highlights` | Highlights | 褒賞 |  |
| `hunts.col.carts` | Carts | 力尽き |  |
| `hunts.col.result` | Result | 結果 |  |
| `hunts.cleared` | Cleared | クリア |  |
| `hunts.failed` | Failed | 失敗 |  |
| `hunts.ofHunt` | of hunt | ハント内 |  |
| `hunts.npc` | (NPC) | （NPC） |  |
| `hunts.title` | Hunts ({count}) — every run, latest first. Click a row for party stats and the damage curve. | ハント（{count}）— すべてのハントを新しい順に。行をクリックするとパーティ統計とダメージカーブを表示。 |  |
| `hunts.search.label` | Search | 検索 |  |
| `hunts.search.placeholder` | Hunt #, hunter, monster, date… | ハント#・ハンター・モンスター・日付… |  |
| `hunts.search.aria` | Search hunts | ハントを検索 |  |
| `hunts.filter.result` | Result filter | 結果で絞り込み |  |
| `hunts.stat.clearTime` | Clear time | クリアタイム |  |
| `hunts.stat.teamDamage` | Team damage | パーティ合計ダメージ |  |
| `hunts.stat.maxHp` | Max HP | 最大HP |  |
| `hunts.stat.enrages` | Enrages | 怒り回数 |  |
| `hunts.loadingCurve` | Loading hunt… | ハントを読み込み中… |  |
| `hunts.damageChart` | Damage chart | ダメージグラフ |  |
| `hunts.chart.sub.burst` | Instantaneous DPS (5s) | 瞬間DPS（5秒） |  |
| `hunts.chart.sub.burst1` | Instantaneous DPS (1s) | 瞬間DPS（1秒） |  |
| `hunts.chart.note` | Red bands: enrage windows. DPS uses {window}, same as Damage curves tab. | 赤い帯は怒り状態の時間帯です。DPSは{window}を使用（ダメージカーブタブと同じ）。 |  |
| `hunts.chart.window.quest` | own first hit→quest end (party last hit) | 自身の初撃→クエスト終了（パーティ最後の一撃） |  |
| `hunts.chart.window.engagement` | engagement time (own first→last hit) | 交戦時間（自身の初撃→最後の一撃） |  |
| `hunts.survival` | Survival | 生存 |  |
| `hunts.survival.sub` | min HP · time in danger | 最小HP · 危険時間 |  |
| `hunts.survival.minHp` | Min HP | 最小HP |  |
| `hunts.highlights` | Hunter highlights | ハンター褒賞 |  |
| `hunts.highlights.sub` | quest awards | クエスト褒賞 |  |
| `hunts.damageShare` | Damage share | ダメージシェア |  |
| `hunts.empty.what` | hunts | ハント |  |
| `hunts.empty.import` | Import hunts with the button above — they land here. | 上のボタンでハントをインポートすると、ここに表示されます。 |  |

## Survival tab
<sub>locales/*/views.survival.json · 35 strings</sub>

| key | English | 日本語 | source |
| --- | --- | --- | --- |
| `survival.axis.dps` | DPS (5s rolling avg) | DPS（5秒移動平均） |  |
| `survival.axis.hp` | hunter HP | ハンターHP |  |
| `survival.axis.time` | time since quest start | クエスト開始からの経過時間 |  |
| `survival.clearedLine` | cleared in {time} | {time} でクリア |  |
| `survival.col.avgHp` | Avg HP | 平均HP |  |
| `survival.col.below25` | < 25% | 25% 未満 |  |
| `survival.col.below50` | < 50% | 50% 未満 |  |
| `survival.col.fullHp` | Full HP | HP満タン |  |
| `survival.col.hunter` | Hunter | ハンター |  |
| `survival.col.minHp` | Min HP | 最小HP |  |
| `survival.col.samples` | Samples | サンプル数 |  |
| `survival.danger.title` | Time in danger | 危険時間 |  |
| `survival.empty.import` | Import hunts first — survival data appears once dumps carry hunter HP. | まずハントをインポートしてください — ハンターHPを含むダンプを読み込むと生存データが表示されます。 |  |
| `survival.empty.what` | hunts | ハント |  |
| `survival.failedLine` | failed after {time} | {time} で失敗 |  |
| `survival.filter.hunt` | Hunt | ハント |  |
| `survival.filter.monsterHp` | Monster HP | モンスターHP |  |
| `survival.legend.dps` | Dashed lines: DPS (left axis). | 破線: DPS（左軸）。 |  |
| `survival.legend.hp` | Solid lines: hunter HP (right axis). | 実線: ハンターHP（右軸）。 |  |
| `survival.legend.noDps` | No DPS for this hunt: the companion wasn’t running, and only the companion records damage over time. | このハントのDPSはありません。コンパニオンが起動しておらず、時間ごとのダメージはコンパニオンのみが記録します。 |  |
| `survival.legend.note` | Averages and time-in-danger ignore gaps over 6 s (loading screens/alt-tabs). HP is sampled ~1 Hz by HuntDumper 0.11+. | 平均と危険時間は6秒を超える空白（ローディング画面や別ウィンドウ操作）を除外します。HPは HuntDumper 0.11+ が約1Hzで取得します。 |  |
| `survival.missing.all` | No hunter HP captured for this hunt. | このハントのハンターHPは取得されていません。 |  |
| `survival.missing.one` | {count} hunter without HP data in this capture. | {count} 人のハンターのHPデータがこの取得分にありません。 |  |
| `survival.missing.other` | {count} hunters without HP data in this capture. | {count} 人のハンターのHPデータがこの取得分にありません。 |  |
| `survival.noHp.after` |  before a quest (it polls party HP once a second); reloading scripts mid-hunt skips that hunt. Older hunts keep their damage curves, but have no survival data. |  を有効にしてください（1秒ごとにパーティHPを取得します）。ハント中にスクリプトを再読み込みすると、そのハントは記録されません。古いハントはダメージカーブのみ保持し、生存データはありません。 |  |
| `survival.noHp.before` | None of these hunts carry per-hunter HP. Enable  | これらのハントにはハンターごとのHPがありません。クエスト開始前に  |  |
| `survival.noHp.openLatest` | Open the latest hunt with HP | HPがある最新のハントを開く |  |
| `survival.noHp.thisHunt` | This hunt has no hunter HP — it predates HP tracking or was captured by an older mod build. Install the current HuntDumper (Settings → Mod) and reload the in-game script. | このハントにはハンターHPがありません — HP記録の導入前か、古いMODで取得されたものです。最新の HuntDumper をインストールし（設定 → MOD）、ゲーム内スクリプトを再読み込みしてください。 |  |
| `survival.noHp.title` | Survival — no hunter HP yet | 生存データ — ハンターHPはまだありません |  |
| `survival.option` | #{id} {monster} · {date} · {players}p | #{id} {monster} · {date} · {players}人 |  |
| `survival.series.dps` | {name} DPS | {name} DPS |  |
| `survival.series.hp` | {name} HP | {name} HP |  |
| `survival.series.monsterHp` | {monster} HP | {monster} HP |  |
| `survival.toggle.hide` | Hide {name} | {name} を隠す |  |
| `survival.toggle.show` | Show {name} | {name} を表示 |  |

## Leaderboard tab
<sub>locales/*/views.leaderboard.json · 9 strings</sub>

| key | English | 日本語 | source |
| --- | --- | --- | --- |
| `leaderboard.col.player` | Player | ハンター |  |
| `leaderboard.col.hunts` | Hunts | ハント数 |  |
| `leaderboard.col.avgDps` | Avg DPS | 平均DPS |  |
| `leaderboard.col.bestDps` | Best DPS | 最高DPS |  |
| `leaderboard.filter.minHunts` | Min hunts | 最小ハント数 |  |
| `leaderboard.empty.scope` | Try a lower min-hunts gate or a different filter combination. | 最小ハント数を下げるか、別のフィルタ条件を試してください。 |  |
| `leaderboard.empty.none` | Try a lower min-hunts gate or import more hunts. | 最小ハント数を下げるか、ハントを追加でインポートしてください。 |  |
| `leaderboard.empty.what` | hunters match these filters | 条件に一致するハンター |  |
| `leaderboard.heading` | Best players by DPS — click a header to sort ({count}) | DPS上位プレイヤー — 見出しをクリックで並べ替え（{count}） |  |

## High scores tab
<sub>locales/*/views.highscores.json · 18 strings</sub>

| key | English | 日本語 | source |
| --- | --- | --- | --- |
| `highscores.col.monster` | Monster | モンスター |  |
| `highscores.col.clear` | Clear | クリアタイム |  |
| `highscores.col.date` | Date | 日付 |  |
| `highscores.col.player` | Player | ハンター |  |
| `highscores.col.weapon` | Weapon | 武器 |  |
| `highscores.col.party` | Party | パーティ |  |
| `highscores.huntTitle` | hunt #{id} | ハント #{id} |  |
| `highscores.solo` | solo | ソロ |  |
| `highscores.filter.top` | Top | 上位 |  |
| `highscores.sort.aria` | Sort leaderboard | ランキングの並べ替え |  |
| `highscores.sort.fastest` | Fastest clear | クリアが速い順 |  |
| `highscores.sort.dps` | Highest DPS | DPSが高い順 |  |
| `highscores.empty.scope` | Try a different filter combination or a hunt they joined. | 別のフィルタ条件か、そのハンターが参加したハントを試してください。 |  |
| `highscores.empty.none` | Try a different filter combination or import more hunts. | 別のフィルタ条件を試すか、ハントを追加でインポートしてください。 |  |
| `highscores.empty.what` | cleared hunts match these filters | 条件に一致するクリア済みハント |  |
| `highscores.heading.dps` | Top {count} hunts by DPS{scoped} ({rows}) | DPS上位 {count} ハント{scoped}（全 {rows} 件） |  |
| `highscores.heading.time` | Top {count} hunts by clear time{scoped} ({rows}) | クリアタイム上位 {count} ハント{scoped}（全 {rows} 件） |  |
| `highscores.scoped` |  — scoped hunters | ・スコープ内 |  |

## Compare tab
<sub>locales/*/views.compare.json · 10 strings</sub>

| key | English | 日本語 | source |
| --- | --- | --- | --- |
| `compare.empty.scope.what` | comparison scope | 比較対象 |  |
| `compare.empty.scope.hint` | Star yourself (and your hunting buddies) with ★ in the hunters bar above, then add them to the scope. | 上のハンターバーで自分（と一緒に狩る仲間）に★を付けて、スコープに追加してください。 |  |
| `compare.empty.hunts.what` | hunts for this scope | このスコープのハント |  |
| `compare.empty.hunts.none` | No hunts include {names} yet. | {names} を含むハントはまだありません。 |  |
| `compare.empty.hunts.fallback` | these hunters | これらのハンター |  |
| `compare.heading` | {label} vs party ({hunts} hunts, {window}-hunt rolling) | {label} 対 パーティ（{hunts} ハント、{window} ハント移動平均） |  |
| `compare.scopeFallback` | scope | スコープ |  |
| `compare.series.partyAvg` | party avg | パーティ平均 |  |
| `compare.series.youRolling` | {label} rolling | {label} 移動平均 |  |
| `compare.series.partyRolling` | party rolling | パーティ移動平均 |  |

## Activity tab
<sub>locales/*/views.activity.json · 12 strings</sub>

| key | English | 日本語 | source |
| --- | --- | --- | --- |
| `activity.empty.what` | activity | アクティビティ |  |
| `activity.empty.hint` | Hunt something first. | まずはハントしてください。 |  |
| `activity.summary.one` | {hunts} hunts · {damage} total damage · {days} active day | {hunts} ハント · 総ダメージ {damage} · 活動日 {days} 日 |  |
| `activity.summary.other` | {hunts} hunts · {damage} total damage · {days} active days | {hunts} ハント · 総ダメージ {damage} · 活動日 {days} 日 |  |
| `activity.chart.hunts` | hunts | ハント数 |  |
| `activity.chart.clearRate` | clear rate | クリア率 |  |
| `activity.table.title` | By day — click a header to sort | 日別 — 見出しをクリックで並べ替え |  |
| `activity.table.date` | Date | 日付 |  |
| `activity.table.hunts` | Hunts | ハント数 |  |
| `activity.table.clearPct` | Clear % | クリア率 % |  |
| `activity.table.avgDps` | Avg DPS | 平均 DPS |  |
| `activity.table.damage` | Damage | ダメージ |  |

## Synergy tab
<sub>locales/*/views.synergy.json · 8 strings</sub>

| key | English | 日本語 | source |
| --- | --- | --- | --- |
| `synergy.table.pairing` | Pairing | ペア |  |
| `synergy.table.hunts` | Hunts | ハント数 |  |
| `synergy.table.clearPct` | Clear % | クリア率 % |  |
| `synergy.table.avgClear` | Avg clear | 平均クリア時間 |  |
| `synergy.table.avgShare` | Avg damage share | 平均ダメージシェア |  |
| `synergy.empty.what` | pairing data for these filters | このフィルタのペアリングデータ |  |
| `synergy.empty.hint` | Try a different filter combination. | 別のフィルタ条件を試してください。 |  |
| `synergy.title` | Teammate pairings ({count}) — click a header to sort | 同行ハンターのペア ({count}) — 見出しをクリックで並べ替え |  |

## Buffs tab
<sub>locales/*/views.buffs.json · 69 strings</sub>

| key | English | 日本語 | source |
| --- | --- | --- | --- |
| `buffs.tablist` | Buffs | バフ |  |
| `buffs.tabs.hunters` | Hunters | ハンター |  |
| `buffs.tabs.monster` | Monster | モンスター |  |
| `buffs.hunt.label` | Hunt | ハント |  |
| `buffs.hunt.option` | #{id} {monster} · {date} · {players}p · {source} | #{id} {monster} · {date} · {players}人 · {source} |  |
| `buffs.hunt.optionNoBuffs` | #{id} {monster} · {date} · {players}p · {source} · no buffs | #{id} {monster} · {date} · {players}人 · {source} · バフなし |  |
| `buffs.source.mod` | mod | MOD |  |
| `buffs.source.companion` | companion | コンパニオン |  |
| `buffs.category.label` | Category | カテゴリ |  |
| `buffs.category.consumables` | Consumables | 消費アイテム |  |
| `buffs.category.skills` | Skills | スキル |  |
| `buffs.category.songs` | Songs | 歌 |  |
| `buffs.category.debuffs` | Debuffs | デバフ |  |
| `buffs.category.palico` | Palico | オトモ |  |
| `buffs.category.unknown` | Unknown | 不明 |  |
| `buffs.agitator.group` | Derived buffs | 派生バフ |  |
| `buffs.agitator.name` | Agitator | 挑戦者 |  |
| `buffs.agitator.title` | Show Agitator uptime, derived from the monster's enrage windows | モンスターの怒り状態から算出した挑戦者の稼働時間を表示 |  |
| `buffs.view.group` | Buffs view | バフ表示 |  |
| `buffs.view.table` | Table | 表 |  |
| `buffs.view.timeline` | Timeline | タイムライン |  |
| `buffs.basis.group` | Uptime basis | 稼働時間の基準 |  |
| `buffs.basis.hunt` | Hunt start | ハント開始 |  |
| `buffs.basis.firstHit` | First hit | 初撃 |  |
| `buffs.basis.noDamage` | No damage data for this hunt | このハントのダメージデータがありません |  |
| `buffs.basis.firstHitTitle` | Measure uptime from first hit ({seconds}s) | 初撃から稼働時間を計測（{seconds}秒） |  |
| `buffs.noHunts.before` | No hunts imported yet. Use the  | ハントがまだ取り込まれていません。クエスト前に |  |
| `buffs.noHunts.after` |  (its own shortcut) before a quest, then Import. | （専用ショートカット）を起動してから「インポート」してください。 |  |
| `buffs.heading` | #{id} {monster} | #{id} {monster} |  |
| `buffs.heading.cleared` | #{id} {monster} · cleared in {time} | #{id} {monster} · {time} クリア |  |
| `buffs.noEnrage.before` | No enrage windows recorded for this hunt, so Agitator cannot be derived. Enrage is recorded by the  | このハントには怒り状態の記録がないため、挑戦者の稼働時間を算出できません。怒り状態は |  |
| `buffs.noEnrage.after` | . | が記録します。 |  |
| `buffs.empty.category` | No {category} data in this hunt. | {category}のデータはこのハントにありません。 |  |
| `buffs.empty.localPlayer` | Buff data is only recorded for the local player. Clear the hunter filter (or select the player who hosted the quest). | バフデータはローカルプレイヤー分のみ記録されます。ハンターフィルタを解除するか、クエストをホストしたプレイヤーを選択してください。 |  |
| `buffs.empty.noBuffs` | The companion recorded no buffs for this hunt. | このハントではコンパニオンがバフを記録していません。 |  |
| `buffs.empty.openLatest` | Open the latest hunt with buffs | バフのある最新のハントを開く |  |
| `buffs.empty.none.before` | No buff/debuff data yet. Run the  | バフ/デバフのデータはまだありません。クエスト前に |  |
| `buffs.empty.none.after` |  (its own shortcut) before a quest. | （専用ショートカット）を起動してください。 |  |
| `buffs.note.table` | Recorded by the HunterPie Analytics companion for the local player. Uptime ends at the party's last hit, not at the results screen. | バフは HunterPie Analytics コンパニオンがローカルプレイヤー分のみ記録します。稼働時間はリザルト画面ではなく、パーティ最後の一撃までです。 |  |
| `buffs.note.tableAgitator` |  Agitator is derived from this hunt's monster enrage windows, not from your build. | 挑戦者はビルドではなく、このハントのモンスターの怒り状態から算出しています。 |  |
| `buffs.note.timeline` | Shaded = active. Hover a block for exact times. Open-ended blocks ran to quest end, and the window ends at the party's last hit rather than at the results screen. | 塗りつぶし = 有効。ブロックにカーソルを合わせると正確な時刻を表示します。終端のないブロックはクエスト終了まで続き、計測はリザルト画面ではなくパーティ最後の一撃で終わります。 |  |
| `buffs.note.timelineAgitator` |  The Agitator lane is derived from the monster's enrage windows. | 挑戦者のレーンはモンスターの怒り状態から算出しています。 |  |
| `buffs.monster.modOnly.before` | Monster statuses are recorded by the  | モンスターの状態異常は |  |
| `buffs.monster.modOnly.after` | . This hunt was captured by the REFramework mod only, which does not track monster statuses. | が記録します。このハントは REFramework MOD のみで取り込まれており、モンスターの状態異常は記録されていません。 |  |
| `buffs.monster.none` | No monster status windows recorded for this hunt. The companion records enrage and ailment activations; older dumps may predate this. | このハントにはモンスターの状態異常の記録がありません。コンパニオンは怒りと状態異常の発動を記録しますが、古いダンプには含まれない場合があります。 |  |
| `buffs.monster.note` | Shaded = status active. Hover a block for exact times and duration (for example, how long a poison lasted). One lane per status, including enrage. | 塗りつぶし = 状態異常が有効。ブロックにカーソルを合わせると正確な時刻と継続時間（例: 毒の持続時間）を表示します。レーンは怒りを含む状態ごとに1本です。 |  |
| `buffs.monster.enrageOnly` | This hunt only has enrage. Poison, stun, mount and the other ailments start with hunts captured by the updated companion build. | このハントには怒り状態しかありません。毒、気絶、乗りなどの状態異常は、更新されたコンパニオンビルドで取り込んだハントから記録されます。 |  |
| `buffs.table.hunter` | Hunter | ハンター |  |
| `buffs.table.category` | Category | カテゴリ |  |
| `buffs.table.abnormality` | Abnormality | バフ/状態 |  |
| `buffs.table.uptime` | Uptime | 稼働時間 |  |
| `buffs.table.pct` | % | % |  |
| `buffs.table.activations` | Activations | 発動回数 |  |
| `buffs.timeline.window` | {player} · {name} · {start}s–{end}s ({duration}s) | {player} · {name} · {start}秒–{end}秒（{duration}秒） |  |
| `buffs.timeline.windowOpen` | {player} · {name} · {start}s–{end}s ({duration}s) · active at quest end | {player} · {name} · {start}秒–{end}秒（{duration}秒） · クエスト終了時も有効 |  |
| `buffs.status.enrage` | Enrage | 怒り |  |
| `buffs.status.ailment.poison` | Poison | 毒 |  |
| `buffs.status.ailment.paralysis` | Paralysis | 麻痺 |  |
| `buffs.status.ailment.sleep` | Sleep | 睡眠 |  |
| `buffs.status.ailment.blast` | Blast | 爆破やられ |  |
| `buffs.status.ailment.exhaust` | Exhaust | 疲労 |  |
| `buffs.status.ailment.stun` | Stun | 気絶 |  |
| `buffs.status.ailment.mount` | Mount | 乗り |  |
| `buffs.status.ailment.flash` | Flash | 閃光 |  |
| `buffs.status.ailment.dung` | Dung Bomb | こやし玉 |  |
| `buffs.status.ailment.tranquilize` | Tranquilize | 捕獲 |  |
| `buffs.status.ailment.offset` | Offset | 相殺 |  |
| `buffs.status.ailment.powerclash` | Power Clash | 押し合い |  |
| `buffs.status.ailment.bleed` | Bleed | 裂傷 |  |

## Weapon classes and shared labels
<sub>locales/*/names.json · 20 strings</sub>

| key | English | 日本語 | source |
| --- | --- | --- | --- |
| `weapon.Greatsword` | Greatsword | 大剣 |  |
| `weapon.SwordAndShield` | Sword & Shield | 片手剣 |  |
| `weapon.DualBlades` | Dual Blades | 双剣 |  |
| `weapon.Longsword` | Long Sword | 太刀 |  |
| `weapon.Hammer` | Hammer | ハンマー |  |
| `weapon.HuntingHorn` | Hunting Horn | 狩猟笛 |  |
| `weapon.Lance` | Lance | ランス |  |
| `weapon.GunLance` | Gunlance | ガンランス |  |
| `weapon.SwitchAxe` | Switch Axe | スラッシュアックス |  |
| `weapon.ChargeBlade` | Charge Blade | チャージアックス |  |
| `weapon.InsectGlaive` | Insect Glaive | 操虫棍 |  |
| `weapon.Bow` | Bow | 弓 |  |
| `weapon.HeavyBowgun` | Heavy Bowgun | ヘビィボウガン |  |
| `weapon.LightBowgun` | Light Bowgun | ライトボウガン |  |
| `name.unknownGear` | Unknown (pre-gear hunts) | 不明（装備情報なしのハント） |  |
| `name.builds` | {n} builds | {n} ビルド |  |
| `name.hunts` | {n} hunts | {n} ハント |  |
| `unit.raw` | raw | 物理 |  |
| `unit.element` | el | 属性 |  |
| `unit.affinity` | affinity | 会心率 |  |

## Quest awards (literal first pass — needs review)

Please replace the 日本語 column with the wording on the quest results screen.
Award names are keyed by id, so a correction also applies to past hunts.

| id | English (captured) | 日本語（初版） | your correction |
| --- | --- | --- | --- |
| 0 | Support All-Star | サポートオールスター |  |
| 1 | Ailment Master | 状態異常マスター |  |
| 2 | Dizzy Pro | スタンのプロ |  |
| 3 | Target Destroyer | ターゲットデストロイヤー |  |
| 4 | Established Hunter | 一流ハンター |  |
| 5 | Master Mounter | 乗りマスター |  |
| 6 | Treasure Hunter | トレジャーハンター |  |
| 7 | Field Researcher | フィールドリサーチャー |  |
| 8 | Slinger Sniper | スリンガースナイパー |  |
| 9 | Survival Expert | サバイバルエキスパート |  |
| 10 | Tool Specialist | ツールスペシャリスト |  |
| 11 | BBQ King | BBQキング |  |
| 12 | Master Angler | 釣りマスター |  |
| 13 | Beast Master | ビーストマスター |  |
| 14 | Stealth Hunter | ステルスハンター |  |
| 15 | Gathering Maniac | 採取マニア |  |
| 16 | Item Addict | アイテム中毒 |  |
| 17 | Obsessed Observer | 執念の観察者 |  |
| 18 | Hit 'Em Where It Hurts! | 弱点を突け！ |  |
| 19 | Beautiful Bombardier | 美しき爆撃手 |  |
| 20 | Social Butterfly | 社交界の蝶 |  |
| 21 | Small Game Monster Hunter | 小物モンスターハンター |  |
| 22 | Slinger Savant | スリンガーの天才 |  |
| 23 | Seikret Sidestep | セクレトステップ |  |
| 24 | Perfect Counters | パーフェクトカウンター |  |
| 25 | Glide Master | 滑空マスター |  |
| 26 | Dual Wielder | 二刀流 |  |
| 27 | Assassination | 暗殺 |  |
| 28 | Weak Point | 弱点 |  |
| 29 | Clasher | 激突王 |  |

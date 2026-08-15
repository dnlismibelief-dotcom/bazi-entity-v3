// 20 名人独立参照四柱生成器（可选、可复现）
//
// 用 lunar-javascript（6tail，与 python 版 lunar_python 同源）生成参照四柱，
// 回写 data/famous20_times.json 的 reference 字段，供 famous20.py --check 比对。
//
// 依赖安装（一次性）:
//   npm install --prefix <dir> lunar-javascript
// 运行:
//   $env:LUNAR_JS='<dir>/node_modules/lunar-javascript'
//   node scripts/famous20_reference.mjs [data/famous20_times.json]
//
// 参照口径（写死在 reference.method 里，比对前必读）:
//   年柱/月柱: 把出生地钟表时刻换算为 UTC+8 绝对时刻，用 lunar-javascript 的
//             getYearInGanZhiExact / getMonthInGanZhiExact（按节气精确切换）。
//   日柱:     取出生地当日（民历日期）正午喂给 lunar-javascript —— 它只依赖
//             日期不依赖钟点，等价于查独立日柱表；换日派按 23 时。
//   时柱:     取出生地当日钟表时刻喂给 lunar-javascript（本批无 23 时生人，
//             不涉及晚子时分歧）。
//   与主引擎的差异（真太阳时、低精度黄经、经度修正）正是 --check 要暴露的对象。

import { createRequire } from 'node:module';
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';

const require = createRequire(import.meta.url);
const LUNAR_JS = process.env.LUNAR_JS || '';
const lunarPkg = resolve(LUNAR_JS || join(dirname(fileURLToPath(import.meta.url)), '..', 'node_modules', 'lunar-javascript'));
const { Solar } = require(lunarPkg);
const pkg = require(join(lunarPkg, 'package.json'));

const dataPath = resolve(process.argv[2] || join(dirname(fileURLToPath(import.meta.url)), '..', 'data', 'famous20_times.json'));
const data = JSON.parse(readFileSync(dataPath, 'utf8'));

function dtParts(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})$/.exec(s);
  if (!m) throw new Error(`bad dt: ${s}`);
  return m.slice(1).map(Number);
}

function lunarAt(year, month, day, hour, minute) {
  return Solar.fromYmdHms(year, month, day, hour, minute, 0).getLunar();
}

let yearExactOk = true, monthExactOk = true;
for (const p of data.people) {
  const [y, mo, d, h, mi] = dtParts(p.dt);

  // 绝对时刻换算到 UTC+8（年/月柱只与绝对时刻有关）
  const utMs = Date.UTC(y, mo - 1, d, h, mi) - p.tz * 3600_000 + 8 * 3600_000;
  const bj = new Date(utMs);
  const lbj = lunarAt(bj.getUTCFullYear(), bj.getUTCMonth() + 1, bj.getUTCDate(),
                      bj.getUTCHours(), bj.getUTCMinutes());
  let refYear, refMonth;
  if (typeof lbj.getYearInGanZhiExact === 'function') {
    refYear = lbj.getYearInGanZhiExact();
  } else { refYear = lbj.getYearInGanZhi(); yearExactOk = false; }
  if (typeof lbj.getMonthInGanZhiExact === 'function') {
    refMonth = lbj.getMonthInGanZhiExact();
  } else { refMonth = lbj.getMonthInGanZhi(); monthExactOk = false; }

  const refDay = lunarAt(y, mo, d, 12, 0).getDayInGanZhi();
  const refHour = lunarAt(y, mo, d, h, mi).getTimeInGanZhi();

  p.reference = {
    source: `lunar-javascript ${pkg.version} (独立参照)`,
    method: '年/月: UTC+8绝对时刻+节气精确切换(get*InGanZhiExact); 日: 出生地民历日正午; 时: 出生地钟表时刻(五鼠遁)',
    year_pillar: refYear,
    month_pillar: refMonth,
    day_pillar: refDay,
    hour_pillar: refHour,
    four_pillars: `${refYear} ${refMonth} ${refDay} ${refHour}`,
  };
}

writeFileSync(dataPath, JSON.stringify(data, null, 2) + '\n', 'utf8');
console.log(`wrote reference pillars for ${data.people.length} people (yearExact=${yearExactOk}, monthExact=${monthExactOk})`);
for (const p of data.people) {
  console.log(`${p.name}\t${p.dt}\t${p.reference.four_pillars}`);
}

// 用法（PowerShell）：
//   $env:WORKLOAD="list_anon"; $env:VUS="50"; k6 run scripts/load/baseline.js
//
// 环境变量：
//   BASE_URL   默认 http://127.0.0.1:18000
//   WORKLOAD   list_anon | list_auth | detail | mix（默认 mix）
//   VUS        稳态并发数，默认 50
//   THINK_TIME 每次迭代后的停顿秒数，默认 0.2（0 = 极限吞吐口径）
//   LIMIT      列表每页条数，默认 20

import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.BASE_URL || 'http://127.0.0.1:18000';
const WORKLOAD = __ENV.WORKLOAD || 'mix';
const VUS = Number(__ENV.VUS || 50);
const THINK = Number(__ENV.THINK_TIME === undefined ? 0.2 : __ENV.THINK_TIME);
const LIMIT = Number(__ENV.LIMIT || 20);

// 阈值跟着负载走：只给本次真正会跑的路径设阈值，
// 否则 k6 会对着一个"没有样本"的指标判红/判绿，结论毫无意义。
const thresholds = {
  http_req_failed: ['rate<0.01'],
};
if (WORKLOAD === 'list_anon' || WORKLOAD === 'mix') {
  thresholds['http_req_duration{path_group:list_anon}'] = ['p(95)<200'];
}
if (WORKLOAD === 'list_auth' || WORKLOAD === 'mix') {
  thresholds['http_req_duration{path_group:list_auth}'] = ['p(95)<400'];
}
if (WORKLOAD === 'detail' || WORKLOAD === 'mix') {
  thresholds['http_req_duration{path_group:detail}'] = ['p(95)<400'];
}

export const options = {
  // 三个 stage：预热 / 稳态 / 收尾。只有稳态段的数据进报告。
  stages: [
    { duration: '30s', target: VUS },
    { duration: '2m', target: VUS },
    { duration: '20s', target: 0 },
  ],
  thresholds,
  // 默认摘要只给 p(90)/p(95)，没有 p(50)/p(99)。
  // 这一行是唯一能改这个行为的地方。
  summaryTrendStats: ['avg', 'min', 'med', 'p(50)', 'p(90)', 'p(95)', 'p(99)', 'max'],
  userAgent: 'k6-baseline/1.0',
};

// ---------- setup：只跑一次，准备 token 和 slug ----------
export function setup() {
  const suffix = Date.now();
  const email = `k6-${suffix}@example.com`;
  const username = `k6${suffix % 100000}`;
  const password = 'k6-password-123';

  const jsonHeaders = { 'Content-Type': 'application/json' };

  // 注册。这个项目注册成功后直接返回 token（RealWorld 规范），不用再登录一次。
  let res = http.post(
    `${BASE}/api/users`,
    JSON.stringify({ username, email, password }),
    { headers: jsonHeaders, tags: { path_group: 'setup' } },
  );

  let token = null;
  if (res.status === 201) {
    token = res.json('user.token');
  } else {
    // 409/422 说明这个邮箱已经存在（比如脚本里忘改 suffix），退化成登录
    res = http.post(
      `${BASE}/api/users/login`,
      JSON.stringify({ email, password }),
      { headers: jsonHeaders, tags: { path_group: 'setup' } },
    );
    if (res.status === 200) {
      token = res.json('user.token');
    }
  }

  // 取一个可用的 slug。列表为空时自己造一篇，否则 detail 场景没有目标。
  let slug = null;
  const listRes = http.get(`${BASE}/api/articles?limit=1`, {
    tags: { path_group: 'setup' },
  });
  if (listRes.status === 200) {
    const body = listRes.json();
    if (body.articles && body.articles.length > 0) {
      slug = body.articles[0].slug;
    }
  }

  if (!slug) {
    const authHeaders = {
      'Content-Type': 'application/json',
      Authorization: `Token ${token}`,
    };
    const created = http.post(
      `${BASE}/api/articles`,
      JSON.stringify({
        article: {
          title: `k6 seed ${suffix}`,
          description: 'created by k6 setup',
          body: 'k6 body. '.repeat(50),
          tagList: ['k6'],
        },
      }),
      { headers: authHeaders, tags: { path_group: 'setup' } },
    );
    if (created.status === 201) {
      slug = created.json('article.slug');
    }
  }

  if (!token || !slug) {
    throw new Error(
      `setup 失败：token=${token ? 'ok' : 'null'} slug=${slug ? 'ok' : 'null'}。` +
        `先确认 ${BASE}/api/articles?limit=1 能返回 200。`,
    );
  }

  console.log(`setup 完成：user=${username} slug=${slug}`);
  return { token, slug, username };
}

// ---------- 三条路径 ----------
function listAnon() {
  const res = http.get(`${BASE}/api/articles?limit=${LIMIT}`, {
    tags: { path_group: 'list_anon' },
  });
  check(res, { 'list_anon 200': (r) => r.status === 200 });
  return res;
}

function listAuth(token) {
  const res = http.get(`${BASE}/api/articles?limit=${LIMIT}`, {
    headers: { Authorization: `Token ${token}` },
    tags: { path_group: 'list_auth' },
  });
  check(res, { 'list_auth 200': (r) => r.status === 200 });
  return res;
}

function detail(slug) {
  const res = http.get(`${BASE}/api/articles/${slug}`, {
    tags: { path_group: 'detail' },
  });
  check(res, { 'detail 200': (r) => r.status === 200 });
  return res;
}

// ---------- 主循环 ----------
export default function (data) {
  if (WORKLOAD === 'list_anon') {
    listAnon();
  } else if (WORKLOAD === 'list_auth') {
    listAuth(data.token);
  } else if (WORKLOAD === 'detail') {
    detail(data.slug);
  } else {
    // mix：一次循环 = 翻列表 + 点进一篇。比单打一个接口更接近真人。
    // 注意 mix 的 QPS 是"两个请求合计"，看单接口数字请用单路径模式。
    listAnon();
    detail(data.slug);
  }

  if (THINK > 0) {
    sleep(THINK);
  }
}

// ---------- 结果落盘 ----------
function fmt(v, digits) {
  return v === undefined || v === null ? 'n/a' : Number(v).toFixed(digits);
}

function groupBlock(metrics, tagName, tagValue) {
  // k6 把带 tag 的指标单独建成一个子指标，名字形如 http_req_duration{path_group:list_anon}。
  // 两个指标要分开取：
  //   http_req_duration（Trend） → 有 P50/P95/P99，但 **没有 count**
  //   http_reqs（Counter）       → 有 count，用它的子指标拿"这条路径发了多少个请求"
  const dur = metrics[`http_req_duration{${tagName}:${tagValue}}`];
  if (!dur) return null;
  const reqs = metrics[`http_reqs{${tagName}:${tagValue}}`];

  const v = dur.values;
  return {
    count: reqs ? reqs.values.count : undefined,
    p50: v['p(50)'],
    p95: v['p(95)'],
    p99: v['p(99)'],
    avg: v.avg,
  };
}

export function handleSummary(data) {
  const m = data.metrics;
  const groups = {};
  for (const g of ['list_anon', 'list_auth', 'detail']) {
    const block = groupBlock(m, 'path_group', g);
    if (block) groups[g] = block;
  }

  const overall = {
    workload: WORKLOAD,
    vus: VUS,
    think_time: THINK,
    limit: LIMIT,
    base_url: BASE,
    http_reqs: m.http_reqs.values.count,
    qps: m.http_reqs.values.rate,
    failed_rate: m.http_req_failed.values.rate,
    duration: {
      p50: m.http_req_duration.values['p(50)'],
      p95: m.http_req_duration.values['p(95)'],
      p99: m.http_req_duration.values['p(99)'],
      max: m.http_req_duration.values.max,
    },
    groups,
  };

  // 文件名里带参数，否则三次跑完只剩最后一份
  const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  const file = `scripts/load/results/${WORKLOAD}-vus${VUS}-think${THINK}-${stamp}.json`;

  // 给终端看的一小段，够贴进报告
  const lines = [
    `---- ${WORKLOAD} | VUs=${VUS} | think=${THINK}s | limit=${LIMIT} ----`,
    `总请求 ${overall.http_reqs}   QPS ${fmt(overall.qps, 1)}   错误率 ${fmt(overall.failed_rate * 100, 2)}%`,
    `P50 ${fmt(overall.duration.p50, 1)}ms  P95 ${fmt(overall.duration.p95, 1)}ms  P99 ${fmt(overall.duration.p99, 1)}ms  max ${fmt(overall.duration.max, 1)}ms`,
  ];
  for (const [k, v] of Object.entries(groups)) {
    lines.push(
      `  ${k.padEnd(10)} n=${v.count}  P50 ${fmt(v.p50, 1)}ms  P95 ${fmt(v.p95, 1)}ms  P99 ${fmt(v.p99, 1)}ms`,
    );
  }

  return {
    [file]: JSON.stringify(overall, null, 2),
    stdout: lines.join('\n') + '\n',
  };
}
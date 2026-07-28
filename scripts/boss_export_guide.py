"""
提示用户从浏览器 DevTools 导数据
完全绕过风控，因为数据直接在用户浏览器里
"""
import json
import subprocess
import webbrowser


BOOKMARKLET_CODE = """javascript:(function(){
  const keywords = ['AI','大模型','人工智能','算法','数据工程','后端开发','产品经理'];
  const cities = ['100010000','100020000','100030000','100040000','100050000'];
  let all = [];
  let done = 0;
  const total = keywords.length * cities.length;
  
  async function fetchPage(kw, city, page) {
    const url = `https://www.zhipin.com/wapi/zpgeek/search/joblist.json?query=${kw}&city=${city}&page=${page}`;
    const resp = await fetch(url, {
      headers: {'x-requested-with':'XMLHttpRequest','zp_token':document.cookie.match(/bst=([^;]+)/)?.[1]||''}
    });
    const data = await resp.json();
    if(data.code !== 0) return [];
    return (data.zpData?.jobList || []).map(j => ({
      url: `https://www.zhipin.com/job_detail/${j.encryptJobId}.html`,
      job_title: j.jobName,
      company_name: j.brandName,
      city: j.cityName,
      salary_min_k: (s=>{let m=s?.match(/(\\d+)(?:K|k)?\\s*[-~–至]\\s*(\\d+)/);return m?parseInt(m[1]):null})(j.salaryDesc),
      salary_max_k: (s=>{let m=s?.match(/(\\d+)(?:K|k)?\\s*[-~–至]\\s*(\\d+)/);return m?parseInt(m[2]):null})(j.salaryDesc),
      education: j.jobDegree,
      experience: j.jobExperience,
      keyword: kw,
      source: 'boss',
      domain: 'zhipin.com',
    }));
  }
  
  (async () => {
    for(const kw of keywords) {
      for(const city of cities) {
        for(let p=1; p<=2; p++) {
          try {
            const jobs = await fetchPage(kw, city, p);
            all.push(...jobs);
          } catch(e) {}
          await new Promise(r => setTimeout(r, 1000));
        }
        done++;
      }
    }
    // 下载 JSON
    const blob = new Blob([JSON.stringify(all,null,2)], {type:'application/json'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'boss_jobs.json';
    a.click();
    console.log('✅ 下载完成:', all.length, '条');
  })();
})();
"""

print("""
╔══════════════════════════════════════════════════════════════╗
║  BOSS直聘 数据导出                                          ║
╚══════════════════════════════════════════════════════════════╝

操作步骤:

1. 在 Brave 浏览器中打开 BOSS直聘并登录
   https://www.zhipin.com/web/geek/job?query=AI&city=100010000

2. 按 F12 打开 DevTools → Console (控制台) 标签

3. 复制下面整段代码, 粘贴到 Console 中, 按回车执行

4. 等待提示 "下载完成" (约 30秒, 会搜索多个关键词和城市)

5. 下载的 boss_jobs.json 文件在 ~/Downloads/ 目录

────────────────────────────────────────────────────────
开始复制 (从下一行到 END):
""")

print("=" * 60)
# 打印可执行的 JS 代码 (非 bookmarklet 格式, 方便 console 粘贴)
js_code = """
(async function(){
  const keywords = ['AI','大模型','人工智能','算法','数据工程','后端开发','产品经理'];
  const cities = ['100010000','100020000','100030000','100040000','100050000'];
  let all = [];
  for(const kw of keywords) {
    for(const city of cities) {
      for(let p=1; p<=2; p++) {
        try {
          const url = `https://www.zhipin.com/wapi/zpgeek/search/joblist.json?query=${kw}&city=${city}&page=${p}`;
          const resp = await fetch(url, {
            headers: {'x-requested-with':'XMLHttpRequest','zp_token':document.cookie.match(/bst=([^;]+)/)?.[1]||''}
          });
          const data = await resp.json();
          if(data.code === 0) {
            for(const j of (data.zpData?.jobList||[])) {
              let salMin=null, salMax=null;
              const m = j.salaryDesc?.match(/(\d+)(?:K|k)?\s*[-~–至]\s*(\d+)/);
              if(m) { salMin=parseInt(m[1]); salMax=parseInt(m[2]); }
              all.push({
                url: `https://www.zhipin.com/job_detail/${j.encryptJobId}.html`,
                job_title: j.jobName, company_name: j.brandName, city: j.cityName,
                salary_min_k: salMin, salary_max_k: salMax,
                education: j.jobDegree, experience: j.jobExperience,
                keyword: kw, source: 'boss', domain: 'zhipin.com'
              });
            }
          }
        } catch(e) { console.warn(kw, city, p, e); }
        await new Promise(r => setTimeout(r, 800));
      }
    }
  }
  const blob = new Blob([JSON.stringify(all,null,2)], {type:'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'boss_jobs.json';
  a.click();
  console.log('✅ 完成! 共 ' + all.length + ' 条, 已下载 boss_jobs.json');
})();
"""
print(js_code)
print("=" * 60)
print("""
────────────────────────────────────────────────────────

完成后:
  cp ~/Downloads/boss_jobs.json ~/projects/pulse-data-engine/data/
  cd ~/projects/pulse-data-engine
  uv run python scripts/import_boss_json.py
""")

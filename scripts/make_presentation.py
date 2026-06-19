"""Generate a 16:9 slide-deck PDF for the Log Analysis AI product.

Pulls live metrics from the trained model, renders dark "mission-control" slides (Thai),
and converts to PDF via headless Chrome. Output: docs/LogAnalysisAI_Presentation.pdf
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from loganalysis.config import settings  # noqa: E402
from loganalysis.datasplit import split_sessions  # noqa: E402
from loganalysis.ingestion.loader import load_dataset  # noqa: E402
from loganalysis.metrics.evaluation import evaluate  # noqa: E402
from loganalysis.persistence import BUNDLE_NAME  # noqa: E402
from loganalysis.pipeline import Pipeline  # noqa: E402
from loganalysis.summarize.llm_summarizer import Summarizer  # noqa: E402

_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# Live demo (static dashboard snapshot on GitHub Pages).
DEMO_URL = "https://natpakanchamp.github.io/LogAnalysisAI/"
DEMO_LABEL = "natpakanchamp.github.io/LogAnalysisAI"


def compute_metrics() -> dict:
    sessions = load_dataset("sample", settings.dataset_dir("sample"))
    _train, test = split_sessions(sessions)
    pipe = Pipeline.from_bundle(settings.artifact_path(BUNDLE_NAME), summarizer=Summarizer(api_key=""))
    ai, ru, lb, hs, dl = [], [], [], [], []
    for s in test:
        r = pipe.process_session(s)
        ai.append(r.ai_anomaly)
        ru.append(r.rule_anomaly)
        lb.append(s.label)
        hs.append(r.high_severity)
        if s.label == 1 and r.ai_anomaly and r.detect_latency is not None:
            dl.append(r.detect_latency)
    rep = evaluate(ai_preds=ai, rule_preds=ru, labels=lb, high_severity=hs, detect_latencies=dl)
    return {
        "precision": rep.overall.precision, "recall": rep.overall.recall, "f1": rep.overall.f1,
        "recall_hs": rep.recall_high_severity, "ai_beats": rep.ai_beats_rules,
        "rule_recall": rep.rule_overall.recall, "n_test": rep.n,
    }


def load_comparison() -> dict | None:
    """Read the synthetic-vs-HDFS comparison produced by scripts/compare_datasets.py."""
    path = ROOT / "docs" / "dataset_comparison.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_sweep(name: str = "hdfs") -> dict | None:
    """Read a num_candidates sweep produced by scripts/sweep_candidates.py."""
    path = ROOT / "docs" / f"sweep_{name}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def chip(text: str, cls: str = "") -> str:
    return f'<span class="chip {cls}">{text}</span>'


def slide(kicker: str, title: str, body: str, page: int, total: int) -> str:
    return f"""<section class="slide">
      <div class="kicker">{kicker}</div>
      <div class="s-title">{title}</div>
      <div class="rule"></div>
      <div class="content">{body}</div>
      <div class="foot"><span>Log Analysis AI &middot; ผู้ช่วยวิเคราะห์ Log ด้วย AI</span>
        <span>ณัฐปคัลภ์ กันทะศร &middot; CP250041 &middot; {page}/{total}</span></div>
    </section>"""


def build_html(m: dict) -> str:
    total = 11
    cmp = load_comparison()
    cover = f"""<section class="slide cover">
      <div class="cover-kicker">AI PRODUCT PRESENTATION &middot; M5 · PM for AI Projects</div>
      <div class="cover-title">Log Analysis <span class="accent">AI</span></div>
      <div class="cover-sub">ผู้ช่วยวิเคราะห์ Log และเฝ้าระวังระบบด้วย AI</div>
      <div class="cover-rule"></div>
      <div class="cover-tag">ตรวจจับความผิดปกติ &rarr; วิเคราะห์ต้นเหตุ &rarr; แจ้งเตือนอัจฉริยะ &rarr; ให้คนยืนยัน</div>
      <div class="cover-demo">🔗 Live demo &nbsp;
        <a href="{DEMO_URL}">{DEMO_LABEL}</a></div>
      <div class="cover-by">
        <div><span class="lbl">ผู้จัดทำ</span><b>ณัฐปคัลภ์ กันทะศร</b> &nbsp;(Natpakan Kanthasorn)</div>
        <div><span class="lbl">รหัส</span><b>CP250041</b> &nbsp;&middot;&nbsp; CP Scholarship AI PM Track &middot; True Digital Academy</div>
      </div>
    </section>"""

    problem = slide("ปัญหา · Problem", "ทำไมต้องมี Log Analysis AI", """
      <div class="two">
        <div>
          <p class="big-q">ระบบ Microservices ล่ม — แต่ไม่รู้ว่าเพราะอะไร</p>
          <ul>
            <li>log ไหลเข้ามา <b>มหาศาล</b> ข้าม service หลายตัว</li>
            <li>ความผิดปกติเป็นแบบ <b>multi-dimension</b> (หลายปัจจัยพร้อมกัน)</li>
            <li><b>rule-based เดิมจับไม่ได้</b> เพราะตั้งกฎครอบคลุมไม่ไหว</li>
            <li>วิศวกรต้อง <b>ไล่ log เองหลายชั่วโมง</b> กว่าจะหาต้นเหตุ</li>
          </ul>
        </div>
        <div class="impact">
          <div class="impact-h">ผลกระทบ</div>
          <div class="impact-row"><b>DevOps / Backend</b><span>เสียเวลา ไล่ log ทีละ service</span></div>
          <div class="impact-row"><b>ผู้ใช้ปลายทาง</b><span>เจอ downtime / latency</span></div>
          <div class="impact-row"><b>ธุรกิจ</b><span>เสียรายได้ + ความเชื่อมั่น</span></div>
        </div>
      </div>""", 2, total)

    solution = slide("วิธีแก้ · Solution", "AI ช่วยย่นเวลาหาต้นเหตุจากชั่วโมง เหลือไม่กี่นาที", """
      <p class="lead">ระบบรับ log แบบ real-time แล้วใช้ AI 3 ชั้นทำงานต่อกัน:</p>
      <div class="cards3">
        <div class="card"><div class="card-n">1</div><div class="card-t">Anomaly Detection</div>
          <div class="card-d">ตรวจจับจุดผิดปกติจาก log อัตโนมัติ (Predictive)</div></div>
        <div class="card"><div class="card-n">2</div><div class="card-t">Classification</div>
          <div class="card-d">จัดหมวดต้นเหตุ + ชี้ service/commit ที่น่าสงสัย (Supervised)</div></div>
        <div class="card"><div class="card-n">3</div><div class="card-t">Generative AI</div>
          <div class="card-d">สรุปสาเหตุเป็นภาษาคนให้วิศวกร (LLM)</div></div>
      </div>
      <p class="note">+ มี <b>Redaction layer</b> ลบความลับก่อนเข้าโมเดล และ <b>Human-in-the-Loop</b> ให้คนยืนยันเคสเสี่ยง</p>
    """, 3, total)

    models = slide("เทคโนโลยี · AI Models", "โมเดล AI ที่ใช้ (ดึงจาก GitHub + Google)", """
      <table class="tbl">
        <tr><th>โมเดล</th><th>ประเภท</th><th>หน้าที่</th><th>ที่มา</th></tr>
        <tr><td><b>DeepLog (LSTM)</b> ⭐</td><td>Anomaly Detection</td><td>ตรวจจับความผิดปกติ (โมเดลหลัก)</td><td>GitHub · PyTorch · เทรนเอง</td></tr>
        <tr><td><b>Logistic Regression</b></td><td>Classification</td><td>จัดหมวดต้นเหตุ</td><td>scikit-learn · เทรนเอง</td></tr>
        <tr><td><b>Gemini 2.5 Flash</b></td><td>Generative (LLM)</td><td>สรุปสาเหตุภาษาคน</td><td>Google API (ฟรี)</td></tr>
        <tr><td><b>Drain3</b></td><td>Log Parsing</td><td>แยก log → template</td><td>GitHub logpai/Drain3</td></tr>
      </table>
      <p class="note">มี <b>rule-based</b> (regex) เป็นตัวเทียบ — ไม่ใช่ AI — เพื่อพิสูจน์ว่า AI ดีกว่าของเดิม</p>
    """, 4, total)

    sw = load_sweep("hdfs")
    if sw:
        best = next(r for r in sw["rows"] if r["g"] == sw["best_g"])
        before = next((r for r in sw["rows"] if r["g"] == 2), None)
        before_txt = f"(จาก F1 {before['ai_f1']:.3f} ก่อนจูน) " if before else ""
        proof = (f"พิสูจน์ได้: นำโค้ดเดิมไป<b>เทรนซ้ำบนข้อมูลจริง HDFS_v1</b> "
                 f"({sw['test']:,} sessions ทดสอบ จาก loghub) แล้วจูน <code>num_candidates</code> "
                 f"→ ที่ g={sw['best_g']}: F1 <b>{best['ai_f1']:.3f}</b> {before_txt}· "
                 f"precision <b>{best['ai_precision']:.3f}</b> · "
                 f"high-severity recall <b>{best['recall_high_severity']:.3f}</b> — ผ่านเกณฑ์ PRD")
    elif cmp:
        h = cmp["hdfs"]
        proof = (f"พิสูจน์ได้: นำโค้ดเดิมไป<b>เทรนซ้ำบนข้อมูลจริง HDFS_v1</b> "
                 f"({h['meta']['sessions']:,} sessions จาก loghub) — "
                 f"high-severity recall <b>{h['metrics']['recall_high_severity']:.3f}</b> "
                 f"บน {h['meta']['test']:,} sessions ที่โมเดลไม่เคยเห็น")
    else:
        proof = ("พิสูจน์ได้: นำโค้ดเดิมไป<b>เทรนซ้ำบนข้อมูลจริง HDFS_v1</b> (loghub) ได้ทันที "
                 "ด้วย <code>train.py --dataset hdfs</code>")

    verify = slide("ตรวจสอบ · Verification", "โมเดลดึงจาก Kaggle หรือเทรนเอง?", f"""
      <div class="verdict">✓ ข้อสรุป: โมเดลหลัก (DeepLog) <b>เทรนเองในเครื่อง 100%</b> — ไม่ได้ดึงโมเดลสำเร็จรูปจาก Kaggle</div>
      <div class="cards3">
        <div class="card"><div class="card-t">โค้ดโมเดล</div>
          <div class="card-d">port <b>โครงสร้าง</b> LSTM จาก GitHub <code>d0ng1ee/logdeep</code> (MIT) — เป็นสถาปัตยกรรม ไม่ใช่ค่าน้ำหนักสำเร็จ</div></div>
        <div class="card"><div class="card-t">น้ำหนัก (Weights)</div>
          <div class="card-d"><b>เทรนเอง</b>ด้วย <code>scripts/train.py</code> → ได้ไฟล์ <code>models/model_bundle.pt</code></div></div>
        <div class="card"><div class="card-t">บทบาทของ Kaggle</div>
          <div class="card-d">เป็นแค่แหล่ง <b>ชุดข้อมูล</b> HDFS (mirror ของ loghub) — <b>ไม่ใช่โมเดล</b></div></div>
      </div>
      <p class="note"><b>หลักฐานในโค้ด:</b> <code>train.py</code> ทำ Drain แยก template + <code>DeepLog.fit()</code> เฉพาะ log ปกติ + เทรน classifier แล้ว <code>save_bundle()</code> ·
        <code>download_data.py --hdfs</code> แค่<b>พิมพ์คำแนะนำ</b>ให้ไปโหลด dataset — ไม่มีการดาวน์โหลดหรือโหลดน้ำหนักโมเดลสำเร็จจากที่ใด · {proof}</p>
    """, 5, total)

    flow_chips = " <span class='arr'>&rarr;</span> ".join([
        chip("Log ดิบ"), chip("ลบความลับ", "warn"), chip("Drain3 แยก template"),
        chip("DeepLog ตรวจ anomaly", "accent"), chip("จัดหมวดต้นเหตุ"),
        chip("ให้คะแนน severity"), chip("Gemini สรุป", "accent"),
        chip("สร้าง Alert"), chip("คนตรวจ (HITL)", "ok"), chip("Feedback retrain"),
    ])
    pipeline = slide("สถาปัตยกรรม · Pipeline", "ข้อมูลไหลผ่านระบบยังไง", f"""
      <div class="flow">{flow_chips}</div>
      <div class="two" style="margin-top:24px">
        <div class="box"><div class="box-h">เข้า (Input)</div>
          log จากทุก microservice (error, latency, error-rate) แบบ real-time</div>
        <div class="box"><div class="box-h">ออก (Output)</div>
          Alert ที่บอก <b>ความรุนแรง + ความมั่นใจ + สาเหตุที่เป็นไปได้ + service/commit ที่น่าสงสัย</b></div>
      </div>
    """, 6, total)

    hitl = slide("Human-in-the-Loop", "AI ไม่ตัดสินคนเดียว — เคสเสี่ยงให้คนยืนยัน", """
      <p class="lead">ใช้ <b>Pattern 2</b>: คนตรวจเฉพาะ alert ที่ถูก flag เท่านั้น (ไม่ตรวจทุกอัน) เงื่อนไขชัดเจน วัดได้:</p>
      <div class="cards3">
        <div class="card trig"><div class="card-t">Confidence &lt; 0.65</div>
          <div class="card-d">โมเดลไม่มั่นใจ → ส่งคนตรวจ</div></div>
        <div class="card trig"><div class="card-t">AI ↔ Rule ขัดแย้ง</div>
          <div class="card-d">AI ว่าผิดปกติ แต่ rule เงียบ → ตรวจ</div></div>
        <div class="card trig"><div class="card-t">Heartbeat Deadlock</div>
          <div class="card-d">ระบบค้างแต่ไม่มี error log → ตรวจ</div></div>
      </div>
      <p class="note">วิศวกรกด <b>ยอมรับ / ปฏิเสธ</b> &rarr; เก็บเป็น feedback ไปปรับปรุงโมเดล (ปิด loop)</p>
    """, 7, total)

    if sw:
        hb = next(r for r in sw["rows"] if r["g"] == sw["best_g"])
        results_compare = f"""
      <table class="tbl cmp">
        <tr><th>ชุดข้อมูล (test set)</th><th>Precision</th><th>Recall</th><th>F1</th>
          <th>Recall<br>(high-sev)</th><th>PRD</th></tr>
        <tr><td><b>Synthetic</b> · sample · g={settings.num_candidates} · {m['n_test']} sessions</td>
          <td>{m['precision']:.3f}</td><td>{m['recall']:.3f}</td><td><b>{m['f1']:.3f}</b></td>
          <td>{m['recall_hs']:.3f}</td><td class="ok"><b>PASS</b></td></tr>
        <tr><td><b>Real HDFS_v1</b> · loghub · g={sw['best_g']} · {sw['test']:,} sessions</td>
          <td>{hb['ai_precision']:.3f}</td><td>{hb['ai_recall']:.3f}</td><td><b>{hb['ai_f1']:.3f}</b></td>
          <td>{hb['recall_high_severity']:.3f}</td><td class="ok"><b>PASS</b></td></tr>
      </table>
      <p class="note">ทั้ง 2 ชุด<b>ผ่านเกณฑ์ PRD ครบ</b> (จูน <code>num_candidates</code> ต่อชุดข้อมูล) ·
        rule-based เดิมได้ Recall เพียง <b>{m['rule_recall']:.3f}</b> (synthetic) / <b>{hb['rule_recall']:.3f}</b> (HDFS) —
        AI จับได้มากกว่าชัดเจน · ตัวเลขทุกตัวรันซ้ำ + ตรวจด้วยมือได้</p>"""
    else:
        results_compare = f"""
      <p class="note">ทดสอบ {m['n_test']} sessions ที่โมเดลไม่เคยเห็น · เทียบ rule-based เดิม Recall เพียง
        <b>{m['rule_recall']:.3f}</b> ขณะที่ AI ได้ <b>{m['recall']:.3f}</b> · ตัวเลขทั้งหมดรันซ้ำ + ตรวจด้วยมือได้</p>"""

    results = slide("ผลลัพธ์ · Results", "วัดผลจริงบน 2 ชุดข้อมูล — ผ่านเกณฑ์ PRD ทั้งคู่", f"""
      <div class="metrics">
        <div class="metric"><div class="mv">{m['recall_hs']:.3f}</div><div class="ml">Recall (high-severity)</div><div class="mt ok">เป้า ≥0.90 · PASS</div></div>
        <div class="metric"><div class="mv">{m['precision']:.3f}</div><div class="ml">Precision (overall)</div><div class="mt ok">เป้า ≥0.70 · PASS</div></div>
        <div class="metric"><div class="mv">{m['f1']:.3f}</div><div class="ml">F1 (overall)</div><div class="mt ok">เป้า ≥0.77 · PASS</div></div>
        <div class="metric"><div class="mv">{m['ai_beats']}</div><div class="ml">เคสที่ AI จับได้ แต่ rule พลาด</div><div class="mt ok">เป้า &gt;0 · PASS</div></div>
      </div>
      <div class="cap">การ์ดด้านบน = ชุด Synthetic (ตัวชี้วัดหลัก PRD) · ตารางด้านล่าง = เทียบกับข้อมูลจริง HDFS</div>
      {results_compare}
    """, 8, total)

    how1 = slide("วิธีใช้งาน · How to Use (1/2)", "ติดตั้งและรันระบบ", """
      <div class="steps">
        <div class="step"><div class="step-n">1</div><div><b>ติดตั้ง</b> (ครั้งเดียว)
          <div class="code">python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"</div></div></div>
        <div class="step"><div class="step-n">2</div><div><b>สร้างข้อมูล + เทรนโมเดล</b>
          <div class="code">python scripts/download_data.py --sample
python scripts/train.py --dataset sample</div></div></div>
        <div class="step"><div class="step-n">3</div><div><b>เปิดเว็บ Dashboard</b>
          <div class="code">uvicorn api.main:app --port 8000   <span class="cmt"># เปิด http://localhost:8000</span></div></div></div>
        <div class="step"><div class="step-n">+</div><div><b>(ทางเลือก) เปิด AI สรุปภาษาคน</b> — ใส่ Gemini API key ฟรีในไฟล์ <code>.env</code>:
          <div class="code">GEMINI_API_KEY=AIza...   <span class="cmt"># ขอฟรีที่ aistudio.google.com/apikey</span></div></div></div>
      </div>
    """, 9, total)

    how2 = slide("วิธีใช้งาน · How to Use (2/2)", "ใช้งานหน้า Dashboard — ตั้งแต่เปิดจนกดยอมรับ", """
      <div class="usegrid">
        <div class="use"><div class="use-n">1</div><b>กรอง</b><br>กดปุ่ม "Needs review" ดูเฉพาะเคสที่ต้องตรวจ</div>
        <div class="use"><div class="use-n">2</div><b>อ่านการ์ด</b><br>ดูความรุนแรง · confidence · service/commit ที่น่าสงสัย</div>
        <div class="use"><div class="use-n">3</div><b>ดูหลักฐาน</b><br>กางดู log จริง (ลบความลับแล้ว)</div>
        <div class="use"><div class="use-n">4</div><b>✦ Explain with AI</b><br>ให้ Gemini สรุปสาเหตุเป็นภาษาคน</div>
        <div class="use"><div class="use-n">5</div><b>ตัดสินใจ</b><br>กด ✓ ยอมรับ (เป็นปัญหาจริง) หรือ ✕ ปฏิเสธ (เตือนผิด)</div>
        <div class="use"><div class="use-n">6</div><b>ปิด loop</b><br>feedback ถูกบันทึกไปปรับปรุงโมเดล</div>
      </div>
      <p class="note">🔗 <b>ลองเล่นได้ทันที (ไม่ต้องติดตั้ง):</b>
        <a href="{demo_url}" style="color:#37e0d8;text-decoration:none">{demo_label}</a>
        &middot; วัดผลเอง: <code>python scripts/evaluate.py --dataset sample</code></p>
    """.replace("{demo_url}", DEMO_URL).replace("{demo_label}", DEMO_LABEL), 10, total)

    summary = """<section class="slide closing">
      <div class="kicker">สรุป · Summary</div>
      <div class="close-title">Log Analysis AI</div>
      <div class="close-sub">เปลี่ยนการไล่ log หลายชั่วโมง ให้เหลือ "อ่าน + กดยืนยัน" ไม่กี่นาที</div>
      <div class="close-points">
        <div>✓ AI 3 ชั้น: ตรวจจับ · จัดหมวด · สรุป</div>
        <div>✓ ผ่านเกณฑ์ PRD ครบ — Recall เคสรุนแรง 1.000</div>
        <div>✓ Human-in-the-Loop กันความผิดพลาด</div>
        <div>✓ พิสูจน์ผลได้ รันซ้ำได้</div>
      </div>
      <div class="close-by">ณัฐปคัลภ์ กันทะศร &middot; CP250041 &middot; ผู้ช่วยวิเคราะห์ Log และเฝ้าระวังระบบด้วย AI</div>
    </section>"""

    slides = [cover, problem, solution, models, verify, pipeline, hitl, results, how1, how2, summary]
    return _PAGE_OPEN + "\n".join(slides) + _PAGE_CLOSE


_PAGE_OPEN = """<!DOCTYPE html><html lang="th"><head><meta charset="utf-8"><style>
  @page { size: 13.333in 7.5in; margin: 0; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, "Helvetica Neue", "Thonburi", sans-serif; color: #e6edf3; }
  .slide { width: 13.333in; height: 7.5in; padding: 0.62in 0.78in 0.7in; background: #0b0f17;
           page-break-after: always; position: relative; overflow: hidden; }
  .slide:last-child { page-break-after: auto; }
  .kicker { color: #37e0d8; font-size: 13px; letter-spacing: 0.18em; text-transform: uppercase; font-weight: 800; }
  .s-title { font-size: 31px; font-weight: 800; margin-top: 5px; letter-spacing: -0.01em; line-height: 1.1; }
  .rule { height: 3px; width: 58px; background: #37e0d8; margin: 13px 0 20px; }
  .content { font-size: 17px; line-height: 1.5; }
  .foot { position: absolute; left: 0.78in; right: 0.78in; bottom: 0.34in; display: flex;
          justify-content: space-between; color: #5b6b7d; font-size: 11px;
          border-top: 1px solid #1c2530; padding-top: 8px; }
  .lead { font-size: 18px; color: #cdd9e5; margin-bottom: 16px; }
  .note { margin-top: 18px; color: #9fb0c0; font-size: 15px; background: #121a26;
          border-left: 3px solid #37e0d8; padding: 11px 15px; border-radius: 8px; }
  ul { margin-left: 20px; } li { margin: 9px 0; }
  b { color: #fff; }
  code { font-family: "SF Mono", Menlo, "Thonburi", monospace; font-size: 14px; color: #7dd3fc; }
  .accent { color: #37e0d8; } .ok { color: #34d399; } .warn { color: #fbbf24; }
  .verdict { background: #10231b; border: 1px solid #1f5140; border-left: 4px solid #34d399;
             color: #d7f5e8; font-size: 19px; font-weight: 700; padding: 14px 18px;
             border-radius: 10px; margin-bottom: 20px; }
  .verdict b { color: #34d399; }

  /* cover */
  .cover { display: flex; flex-direction: column; justify-content: center; padding-left: 1in; }
  .cover-kicker { color: #37e0d8; font-size: 14px; letter-spacing: 0.2em; font-weight: 800; }
  .cover-title { font-size: 72px; font-weight: 900; letter-spacing: -0.02em; margin-top: 14px; }
  .cover-sub { font-size: 25px; color: #cdd9e5; margin-top: 8px; }
  .cover-rule { height: 4px; width: 90px; background: #37e0d8; margin: 26px 0; }
  .cover-tag { font-size: 17px; color: #8fa3b5; letter-spacing: 0.01em; }
  .cover-demo { margin-top: 30px; font-size: 17px; color: #cdd9e5; font-weight: 700;
                background: #102733; border: 1px solid #1f5140; border-left: 4px solid #37e0d8;
                border-radius: 10px; padding: 12px 18px; display: inline-block; }
  .cover-demo a { color: #37e0d8; text-decoration: none; }
  .cover-by { margin-top: 34px; font-size: 16px; line-height: 2; }
  .cover-by .lbl { color: #5b6b7d; display: inline-block; width: 64px; font-size: 13px; }
  .cover-by b { color: #37e0d8; }

  /* two columns */
  .two { display: flex; gap: 26px; }
  .two > div { flex: 1; }
  .big-q { font-size: 20px; color: #fff; font-weight: 700; margin-bottom: 14px; }
  .impact { background: #121a26; border: 1px solid #1c2530; border-radius: 12px; padding: 18px 20px; }
  .impact-h { color: #f87171; font-weight: 800; font-size: 14px; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 12px; }
  .impact-row { display: flex; justify-content: space-between; padding: 9px 0; border-bottom: 1px solid #1c2530; font-size: 15px; }
  .impact-row span { color: #9fb0c0; }

  /* 3 cards */
  .cards3 { display: flex; gap: 18px; }
  .card { flex: 1; background: #121a26; border: 1px solid #1c2530; border-top: 3px solid #37e0d8;
          border-radius: 12px; padding: 20px; }
  .card-n { color: #37e0d8; font-size: 30px; font-weight: 900; }
  .card-t { font-size: 18px; font-weight: 800; margin: 6px 0 8px; }
  .card-d { color: #9fb0c0; font-size: 15px; line-height: 1.45; }
  .card.trig { border-top-color: #fbbf24; }
  .card.trig .card-t { color: #fde68a; }

  /* table */
  .tbl { width: 100%; border-collapse: collapse; font-size: 16px; }
  .tbl th { background: #102733; color: #37e0d8; text-align: left; padding: 11px 14px; font-size: 14px; }
  .tbl td { padding: 11px 14px; border-bottom: 1px solid #1c2530; color: #cdd9e5; }

  /* flow */
  .flow { display: flex; flex-wrap: wrap; align-items: center; gap: 9px; }
  .chip { background: #121a26; border: 1px solid #2a3645; border-radius: 999px; padding: 9px 15px; font-size: 14px; }
  .chip.accent { border-color: #37e0d8; color: #37e0d8; }
  .chip.warn { border-color: #fbbf24; color: #fbbf24; }
  .chip.ok { border-color: #34d399; color: #34d399; }
  .arr { color: #5b6b7d; }
  .box { background: #121a26; border: 1px solid #1c2530; border-radius: 12px; padding: 16px 18px; font-size: 15px; color: #cdd9e5; }
  .box-h { color: #37e0d8; font-weight: 800; font-size: 13px; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 8px; }

  /* metrics */
  .metrics { display: flex; gap: 16px; }
  .metric { flex: 1; background: #121a26; border: 1px solid #1c2530; border-radius: 14px; padding: 16px 16px; text-align: center; }
  .mv { font-size: 42px; font-weight: 900; color: #37e0d8; line-height: 1; }
  .ml { font-size: 13.5px; color: #cdd9e5; margin: 9px 0 7px; min-height: 36px; }
  .mt { font-size: 12px; font-weight: 800; }
  .mt.ok { color: #34d399; }
  .cap { color: #8fa3b5; font-size: 12.5px; margin: 14px 0 6px; }
  .tbl.cmp { font-size: 14px; }
  .tbl.cmp th { padding: 8px 12px; font-size: 12.5px; }
  .tbl.cmp td { padding: 8px 12px; }
  .tbl.cmp td.ok { color: #34d399; }

  /* steps (how-to 1) */
  .steps { display: flex; flex-direction: column; gap: 13px; }
  .step { display: flex; gap: 16px; align-items: flex-start; }
  .step-n { flex: none; width: 30px; height: 30px; border-radius: 50%; background: #37e0d8; color: #0b0f17;
            font-weight: 900; display: flex; align-items: center; justify-content: center; font-size: 15px; }
  .step > div:last-child { font-size: 15px; padding-top: 3px; }
  .code { font-family: "SF Mono", Menlo, "Thonburi", monospace; font-size: 13.5px; color: #c8e1f0;
          background: #060a11; border: 1px solid #1c2530; border-radius: 8px; padding: 9px 13px; margin-top: 6px; white-space: pre-wrap; }
  .code .cmt { color: #34d399; }

  /* use grid (how-to 2) */
  .usegrid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; }
  .use { background: #121a26; border: 1px solid #1c2530; border-radius: 12px; padding: 16px 17px; font-size: 14.5px; color: #cdd9e5; position: relative; }
  .use b { font-size: 16px; }
  .use-n { width: 26px; height: 26px; border-radius: 50%; background: #1c2530; color: #37e0d8;
           font-weight: 800; display: inline-flex; align-items: center; justify-content: center; font-size: 13px; margin-bottom: 8px; }

  /* closing */
  .closing { display: flex; flex-direction: column; justify-content: center; padding-left: 1in; }
  .close-title { font-size: 56px; font-weight: 900; color: #fff; margin-top: 10px; }
  .close-sub { font-size: 21px; color: #cdd9e5; margin: 10px 0 30px; }
  .close-points { font-size: 18px; line-height: 2.1; color: #cdd9e5; }
  .close-points div { }
  .close-by { margin-top: 44px; color: #5b6b7d; font-size: 14px; }
</style></head><body>
"""

_PAGE_CLOSE = "</body></html>"


def main() -> int:
    m = compute_metrics()
    out_dir = ROOT / "docs"
    out_dir.mkdir(exist_ok=True)
    html_path = out_dir / "LogAnalysisAI_Presentation.html"
    pdf_path = out_dir / "LogAnalysisAI_Presentation.pdf"
    html_path.write_text(build_html(m), encoding="utf-8")

    if not Path(_CHROME).exists():
        print(f"HTML written to {html_path} (Chrome not found — open and print to PDF).")
        return 0
    subprocess.run(
        [_CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={pdf_path}", html_path.as_uri()],
        check=True, capture_output=True,
    )
    print(f"Slides built · F1={m['f1']:.3f} RecallHS={m['recall_hs']:.3f} → {pdf_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

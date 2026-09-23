#!/usr/bin/env python3

import json
from pathlib import Path
import sys


KINDS = {"run": 0, "compile": 1, "install": 2, "discard": 3, "malformed": 4, "summary": 5}
SCOPES = {"first": 0, "same_runtime": 1, "same_process": 2, "cross_process": 3}


def compact(workload):
    prior = {}
    pointer_repeats = {"same": 0, "different": 0}
    recurrence = {kind: {scope: 0 for scope in SCOPES}
                  for kind in ("guest", "self_hosted", "system")}
    previous = {kind: {} for kind in recurrence}
    candidate_script_addresses = {}
    same_runtime_scripts = {kind: {"different_pointer": 0, "same_pointer": 0,
                                   "same_pointer_after_discard_and_compile": 0}
                            for kind in recurrence}
    for event in workload["events"]:
        if event["event"] == "install":
            kind = event["provenance"]
            if kind != "guest" or event["key_has_source"]:
                key = tuple(event["cache_key"])
                earlier = previous[kind].get(key)
                if earlier is None:
                    scope = "first"
                elif earlier["pid"] != event["pid"]:
                    scope = "cross_process"
                elif earlier["runtime"] != event["runtime"]:
                    scope = "same_process"
                else:
                    scope = "same_runtime"
                recurrence[kind][scope] += 1
                if scope == "same_runtime":
                    if earlier["script"] == event["script"]:
                        same_runtime_scripts[kind]["same_pointer"] += 1
                        same_runtime_scripts[kind]["same_pointer_after_discard_and_compile"] += (
                            earlier.get("discard_event_index") is not None
                            and event.get("compile_event_index") is not None)
                    else:
                        same_runtime_scripts[kind]["different_pointer"] += 1
                previous[kind][key] = event
        if event["event"] != "install" or "key_id" not in event:
            continue
        key = event["key_id"]
        identity = (event["pid"], event["script"])
        candidate_script_addresses.setdefault(key, set()).add(identity)
        if key in prior:
            pointer_repeats["same" if prior[key] == identity else "different"] += 1
        prior[key] = identity
    sources = sorted({e["filename"] for e in workload["events"] if e["event"] == "install"})
    source_ids = {name: i for i, name in enumerate(sources)}
    keys = [[source_ids[k["filename"]], k["installs"], k["cache_bytes_min"],
             k["cache_bytes_max"], k["runtime_count"]] for k in workload["keys"]]
    ten_install_keys = [k for k in workload["keys"] if k["installs"] == 10]
    events = [[e.get("elapsed_us"), KINDS[e["event"]], e.get("pid"), e.get("key_id"),
               e.get("compile_us", e.get("duration_us")), e.get("cache_bytes"),
               SCOPES.get(e.get("recurrence_scope")), source_ids.get(e.get("filename")),
               e.get("link_us"), e.get("lifetime_us")] for e in workload["events"]]
    timeline = {}
    timeline_origin_us = min((e["elapsed_us"] for e in workload["events"]
                              if e["event"] == "install" and "key_id" in e), default=0)
    for e in workload["events"]:
        if e["event"] != "install" or "key_id" not in e:
            continue
        second = (e["elapsed_us"] - timeline_origin_us) // 1_000_000
        bucket = timeline.setdefault(second, [0, 0])
        bucket[0] += 1
        bucket[1] += e["recurrence_scope"] != "first"
    fields = ("record_id", "manifest", "recording", "counts", "candidate",
              "event_links", "distributions", "cache_models", "capacity_curve",
              "unique_footprint_bytes", "top_sources", "provenance_summary")
    return {key: workload[key] for key in fields} | {
        "firefox_revisions": sorted({e["firefox_revision"] for e in workload["events"]
                                     if e["event"] == "run" and "firefox_revision" in e}),
        "sources": sources, "keys": keys, "events": events,
        "pointer_repeats": pointer_repeats,
        "ten_install_pattern": {
            "keys": len(ten_install_keys),
            "distinct_script_addresses": sum(
                len(candidate_script_addresses[k["id"]]) == 10 for k in ten_install_keys),
        },
        "recurrence_by_provenance": recurrence,
        "same_runtime_script_pointers": same_runtime_scripts,
        "timeline_origin_us": timeline_origin_us,
        "timeline": [[second, *timeline[second]] for second in sorted(timeline)],
    }


def main():
    source, destination = map(Path, sys.argv[1:3])
    report = json.loads(source.read_text())
    patch_directory = Path(__file__).parent / "patches"
    patches = json.loads((patch_directory / "series.json").read_text())
    patches["filename"] = "baseline-cache-instrumentation.patch"
    patches["mbox"] = "".join((patch_directory / name).read_text() for name in patches["files"])
    data = {"methodology": report["methodology"],
            "patches": patches,
            "workloads": {name: compact(w) for name, w in report["workloads"].items()}}
    encoded = json.dumps(data, separators=(",", ":")).replace("<", "\\u003c")
    destination.write_text(HTML.replace("__DATA__", encoded))


HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Global Baseline Compilation Cache Trace Simulation</title>
<style>
:root{--paper:#f5f4ef;--card:#fffefa;--ink:#182b2b;--muted:#657575;--rule:#d6dfda;--teal:#087f75;--gray:#bac9c3;--blue:#6381ac;--orange:#cd694a}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
header{background:#103136;color:#f8f7f2;padding:40px max(24px,calc((100vw - 1220px)/2)) 33px}
header small{font:700 11px ui-monospace,monospace;letter-spacing:.15em;text-transform:uppercase;color:#9cd9ce}
h1{font-size:clamp(30px,4vw,50px);letter-spacing:-.05em;line-height:1.08;margin:13px 0;max-width:800px}
header p{color:#c4d8d3;max-width:850px;margin:0}header .meta{display:flex;gap:32px;flex-wrap:wrap;margin-top:26px;font:11px ui-monospace,monospace;color:#a6c2bc}
header .meta b{display:block;color:white;font-size:18px;margin-top:2px}
nav{position:sticky;top:0;z-index:5;background:var(--card);border-bottom:1px solid var(--rule);overflow:auto}
nav div{max-width:1220px;margin:auto;display:flex;gap:22px;padding:10px 24px;white-space:nowrap}
nav a{font-size:13px;color:var(--muted);text-decoration:none}nav a:hover,a{color:var(--teal)}
main{max-width:1220px;margin:auto;padding:28px 24px 90px}
section{margin-bottom:50px}h2{font-size:26px;letter-spacing:-.04em;margin:0 0 10px;border-bottom:1px solid var(--rule);padding-bottom:9px}
h3{font-size:15px;margin:0 0 6px}.sub{color:var(--muted);margin:0 0 17px;max-width:950px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.two{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.card{background:var(--card);border:1px solid var(--rule);border-radius:10px;padding:18px;min-width:0}
.card .value{font-size:34px;font-weight:750;letter-spacing:-.06em;font-variant-numeric:tabular-nums}
.card .label{font:700 11px ui-monospace,monospace;letter-spacing:.09em;color:var(--muted);text-transform:uppercase}
.small{font-size:12px;color:var(--muted)}.note{background:#e5f0eb;border-left:4px solid var(--teal);padding:13px 17px;margin:17px 0 0;border-radius:0 7px 7px 0}
.warn{background:#fff0e6;border-color:var(--orange)}.controls{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin:0 0 13px}
label{font-size:12px;color:var(--muted)}select,input,button{font:inherit;color:var(--ink);background:var(--card);border:1px solid #b8c6c0;border-radius:6px;padding:6px 9px}
label select,label input{display:block;margin-top:4px}button{cursor:pointer}.download{display:inline-block;background:#103136;color:#fff;text-decoration:none;border-radius:6px;padding:9px 14px;margin-block:6px 12px}.download:hover{background:var(--teal)}button.active{background:#103136;color:#fff;border-color:#103136}
.tabs{display:flex;flex-wrap:wrap;gap:7px}.tabs button{font-size:13px}
.stack-row{display:grid;grid-template-columns:135px 1fr 100px;align-items:center;gap:13px;margin:15px 0}
.stack{height:26px;background:#e8efeb;display:flex;overflow:hidden;border-radius:4px}.stack div{height:100%}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:var(--muted);margin-top:13px}.legend i{display:inline-block;width:10px;height:10px;margin-right:5px}
.chart{width:100%;height:230px;display:block}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:8px;border-bottom:1px solid var(--rule);vertical-align:top}
th{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.07em}.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.scroll{overflow:auto}.source{font:11px/1.4 ui-monospace,monospace;word-break:break-all}
.bar{height:12px;background:#e5ece8;border-radius:3px;overflow:hidden;min-width:100px}.bar span{height:100%;background:var(--teal);display:block}
.event-controls{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.event-controls select,.event-controls input{width:100%;min-width:0}
#event-rows tr{cursor:pointer}#event-rows tr:hover,#event-rows tr.selected{background:#e5f0eb}#event-rows .source{max-width:420px}
pre{background:#103136;color:#e6f5ee;border-radius:7px;padding:14px;overflow:auto;max-height:230px;min-height:80px;font:12px/1.5 ui-monospace,monospace;white-space:pre-wrap;word-break:break-word}
.provenance{font:11px/1.6 ui-monospace,monospace;color:var(--muted);overflow-wrap:anywhere}
.lifecycle{padding-inline-start:1.8rem;margin-block:20px;display:grid;gap:12px}
.lifecycle>li{padding:18px 22px}.lifecycle>li::marker{font-weight:750;color:var(--teal)}
.lifecycle p{margin-block:8px}.lifecycle-lookup{border-inline-start:4px solid var(--teal)}
.lifecycle-heading{margin-block:24px 12px}
.lifecycle-metrics{min-inline-size:620px}.lifecycle-metrics th[scope=row]{text-transform:none;letter-spacing:normal;font-size:13px;color:var(--ink);inline-size:18%}
footer{border-top:1px solid var(--rule);padding-top:16px;color:var(--muted);font-size:12px}
@media(max-width:850px){.grid3,.two{grid-template-columns:1fr}.event-controls{grid-template-columns:1fr 1fr}}
@media(max-width:550px){main{padding:20px 14px 60px}header{padding:28px 16px}nav div{padding:10px 14px}.event-controls{grid-template-columns:1fr}.stack-row{grid-template-columns:1fr}}
</style>
</head>
<body>
<header>
<small>AmberMonkey · OOPSLA 2027 · Fossil 0–1</small>
<h1>Global Baseline Compilation Cache Trace Simulation</h1>
<p>A trace-driven cache simulation of benchmark and manual browser recordings. Observed Baseline compilation and installation are separated from what an idealized immutable cache might retain.</p>
<div class="meta" id="meta"></div>
</header>
<nav><div><a href="#overview">Overview</a><a href="#terms">Compilation lifecycle</a><a href="#recurrence">Recurrence</a><a href="#capacity">Cache capacity</a><a href="#distribution">Distributions</a><a href="#sources">Sources</a><a href="#timeline">Timeline</a><a href="#events">Events</a><a href="#method">Method</a><a href="#patches">Download patches</a></div></nav>
<main>
<section id="overview"><h2>At a glance</h2><p class="sub">One browser recording per workload. A candidate is a guest Baseline install with a source fingerprint.</p><div class="grid3" id="cards"></div><p class="note" id="overview-note"></p></section>
<section id="terms">
<h2>Compilation lifecycle: what an installation means</h2>
<p class="note"><b>In the recorded engine, a Baseline installation follows a fresh compilation.</b> This applies to first and repeated installations alike. A repeated candidate key identifies compilation work that a compatible code cache could potentially avoid. The recordings do not use the proposed cache; all cache hits in this dashboard are simulated.</p>
<h3>The recorded path</h3>
<ol class="lifecycle">
<li class="card"><h3>A script needs Baseline code</h3><p>A JSScript contains bytecode created or loaded for a script instance. Tiering or eager compilation triggers Baseline compilation when that script needs native code. A page reload or a recreated frame can create another JSScript for the same source, even within the same JSRuntime.</p></li>
<li class="card"><h3>The backend compiles fresh machine code</h3><p>The engine generates Baseline code on the main thread or a helper thread. The <code>compile</code> event records the end of this work, its duration and whether it succeeded. A matching candidate key from an earlier compilation does not bypass this step in the recorded path.</p></li>
<li class="card"><h3>The engine links and installs the compiled code</h3><p>Finalization links executable code, allocates BaselineScript metadata, sets up mappings and attaches the result to the JSScript. The <code>install</code> event marks that completed attachment; <code>link_us</code> measures the finalization path through attachment, separately from backend compilation.</p><p><b>A repeated installation therefore follows another compilation.</b> It can attach code to a new script instance or replace code previously discarded from an existing script. “First” and “repeated” refer to the candidate key's history in this recording.</p></li>
<li class="card"><h3>The script executes until its code is discarded</h3><p>Calling a script that already has Baseline code reuses its attachment. These calls produce no new installation and do not refresh the simulated LRU. A <code>discard</code> event marks removal of the attachment. If the script later needs Baseline code again, it must obtain it again.</p></li>
</ol>
<div class="card lifecycle-lookup">
<h3>Where a cache could save compilation</h3>
<p>A proposed cache would look for a compatible, ready body <b>before backend compilation</b>. On a hit, the engine could reuse that body and skip step 2, while still performing the binding and attachment needed by this script. On a miss, it would compile a fresh body and make it available for later reuse.</p>
<p><b>The savings target is repeated backend compilation.</b> The compile-time sum at simulated hits measures recorded work that could potentially be avoided. The link-time sum is reported separately: reusing a body does not eliminate all finalization work. Parsing, bytecode creation, cache lookup, loading and per-script state also remain relevant costs.</p>
<p class="small">Repeated keys are candidates for reuse, subject to compatible compilation inputs, cache capacity and the body being ready when requested. Summed helper-thread durations can overlap other work, so compilation time avoided is not a prediction of elapsed benchmark time saved.</p>
</div>
<h3 class="lifecycle-heading">What the current metrics can establish</h3>
<div class="card scroll"><table class="lifecycle-metrics"><thead><tr><th>Metric</th><th>How it is calculated</th><th>Implication for the proposed cache</th></tr></thead><tbody>
<tr><th scope="row">Eligible installs</th><td>Successful guest attachments with a source fingerprint.</td><td>A proxy for requests that reached installation. The trace does not identify all eligible requests, including those that fail or are cancelled before attachment.</td></tr>
<tr><th scope="row">Candidate keys</th><td>Distinct tuples of filename, source extent and encoding, source and bytecode hashes, immutable flags, and debug instrumentation.</td><td>A working approximation to reusable body identity. It is not a hash of native code or a proven equivalence relation for the proposed compiler. Source locations can split reusable bodies; unrecorded compilation inputs can distinguish bodies that this key groups together.</td></tr>
<tr><th scope="row">Repeated installs</th><td>Eligible installs minus distinct candidate keys in this recording.</td><td>Counts potentially avoidable repeated compilations. Dividing by eligible installs gives the unlimited-cache repeat fraction under the identity and availability assumptions. A finite cache can miss on a repeat after eviction.</td></tr>
<tr><th scope="row">LRU hit rate</th><td>Simulated hits divided by eligible installs. Each install looks up its key, refreshes recency on a hit, or immediately inserts an entry on a miss if it fits.</td><td>Lookups and fills occur at installation time in this model. To estimate the proportion of actual requests served, replay request events and body publication separately, in their respective orders.</td></tr>
<tr><th scope="row">Entry bytes</th><td>Selected observed size: instructions, allocated JitCode, or code plus BaselineScript metadata. The ordinary models retain the size recorded on admission.</td><td>These are current allocation proxies. A process-independent body's size must account for its reusable representation and metadata; private per-script state belongs in a separate budget. Size-splitting diagnoses variation but does not validate identity.</td></tr>
<tr><th scope="row">Compile and link sums at hits</th><td>Observed durations associated with installs classified as hypothetical hits.</td><td>Weights on the potential work avoided. Lookup, loading, binding and synchronization still cost time; helper-thread work may overlap other execution. These sums do not predict benchmark speedup.</td></tr>
<tr><th scope="row">Recurrence gap</th><td>Wall-clock time between consecutive installs with one candidate key.</td><td>Shows spacing between repeated completed compilations under the proxy. Cache eviction depends on intervening requests and admitted bytes; a long or short time gap alone does not determine a hit.</td></tr>
</tbody></table></div>
<p class="note warn"><b>The existing replay estimates reuse among completed Baseline compilations.</b> A simulation of requests served by process-independent bodies needs a request identifier and timestamp, a defensible body identity, a body-ready event and stored size, and an explicit policy for concurrent requests and cache ownership. Installation remains useful for checking outcomes and measuring binding costs.</p>
</section>
<section id="recurrence"><h2>Where recurrence occurs</h2><p class="sub">Each completed installation is classified against the most recent earlier install with the same candidate key. These labels locate repeated demand; they do not indicate a cache hit or the absence of compilation. Select a code kind to compare workloads.</p><div class="controls"><div class="tabs" id="recurrence-tabs"></div></div><div class="card"><div id="stacks"></div><div class="legend"><span><i style="background:var(--gray)"></i>First install</span><span><i style="background:var(--teal)"></i>Same JSRuntime</span><span><i style="background:var(--blue)"></i>Same process, other JSRuntime</span><span><i style="background:var(--orange)"></i>Other process</span></div></div><p class="note"><b>First install</b> is the first observation of a key in this recording. <b>Same JSRuntime</b> means the preceding matching install has the same PID and runtime address; <b>same process, other JSRuntime</b> means the PID matches but the runtime address differs; <b>other process</b> means the PID differs. A JSRuntime can contain many script instances. All four categories describe recorded completions; none identifies a cache service outcome. Comparing only the most recent occurrence also does not measure the extra hits a shared cache would provide over separate caches.</p><p class="small" id="recurrence-note"></p><h3 style="margin-top:20px">Cross-process recurrence by provenance</h3><div class="card scroll"><table id="provenance-table"></table></div><p class="small" id="cross-process-note"></p></section>
<section id="capacity"><h2>What fits?</h2><p class="sub">Global exact-key LRU replay, counted across all processes in each recording.</p><div class="controls"><div class="tabs" id="capacity-tabs"></div><label>Size assumption<select id="size-model"><option value="instructions">Instructions only</option><option value="allocated_code">Allocated JitCode</option><option value="code_plus_metadata" selected>Code + BaselineScript</option><option value="code_plus_metadata_size_split">Code + metadata, split differing sizes</option></select></label></div><p id="capacity-timing"></p><div class="two"><div class="card"><canvas class="chart" id="capacity-chart"></canvas><p class="small">Proxy hit rate: simulated hits / eligible completed installations. Requests and body publication are both replayed at install time. Curves compare allocation assumptions; capacity limits retained entries, not total live browser memory.</p></div><div class="card scroll"><table id="capacity-table"></table></div></div><p class="small" id="capacity-timing-coverage"></p><p class="small">Compile avoided sums recorded backend durations at simulated hits; share is relative to total eligible compile time. Linking and installation are excluded. Helper-thread work can overlap other execution, and cache lookup and binding still cost time, so these are potential work savings, not elapsed benchmark time saved. The table shows six selected capacities; the graph retains all samples through 16 MiB.</p><p class="note" id="capacity-note"></p></section>
<section id="distribution"><h2>Cost and size distributions</h2><p class="sub">Log-spaced histograms show the range behind medians and means.</p><div class="controls"><label>Workload<select id="distribution-workload"></select></label><label>Measure<select id="distribution-measure"><option value="compile">Compile duration (µs)</option><option value="size">Cache entry bytes</option><option value="gap">Recurrence gap (ms)</option></select></label></div><div class="two"><div class="card"><canvas class="chart" id="distribution-chart"></canvas><p class="small" id="distribution-note">Zero values are included in the first bin.</p></div><div class="card scroll"><table id="distribution-table"></table></div></div></section>
<section id="sources"><h2>Sources driving repeats</h2><p class="sub">Filename groups expose concentration; these labels are provenance, not a validated cache identity.</p><div class="controls"><label>Workload<select id="source-workload"></select></label></div><div class="card scroll"><table id="source-table"></table></div></section>
<section id="timeline"><h2>When code returns</h2><p class="sub">One-second bins from the first eligible Baseline install in each recording.</p><div class="controls"><label>Workload<select id="timeline-workload"></select></label></div><div class="card"><canvas class="chart" id="timeline-chart"></canvas><p class="small" id="timeline-note"></p></div></section>
<section id="events"><h2>Event explorer</h2><p class="sub">Recorded compile, install, and discard events appear in timestamp order. The adjacent <a href="0-1-baseline-cache-simulation-detail.json">full JSON artifact</a> retains every original field and event link.</p><div class="card"><div class="event-controls controls"><label>Workload<select id="event-workload"></select></label><label>Type<select id="event-kind"><option value="all">All</option><option value="compile">Compile</option><option value="install">Install</option><option value="discard">Discard</option></select></label><label>Recurrence<select id="event-scope"><option value="all">All</option><option value="first">First</option><option value="same_runtime">Same JSRuntime</option><option value="same_process">Same process, other JSRuntime</option><option value="cross_process">Other process</option></select></label><label>Source contains<input id="event-search" placeholder="Filename or URL"></label></div><p class="small" id="event-count"></p><div class="scroll"><table><thead><tr><th>#</th><th>Time</th><th>Type</th><th>PID</th><th>Key</th><th>Compile</th><th>Entry</th><th>Scope</th><th>Source</th></tr></thead><tbody id="event-rows"></tbody></table></div><div class="controls" style="margin-top:14px"><button id="prev">Previous</button><span class="small" id="page"></span><button id="next">Next</button></div><pre id="event-detail">Select an event to inspect its fields.</pre></div></section>
<section id="method"><h2>Method and limits</h2><div class="two"><div class="card"><h3>Identity</h3><p id="method-key"></p><h3>Candidate population</h3><p id="method-candidate"></p></div><div class="card"><h3>Replay and timing</h3><p id="method-cache"></p><p id="method-sizes"></p><p id="method-timing"></p></div></div><p class="note warn" id="method-limits"></p><div class="card" style="margin-top:14px"><h3>Run provenance</h3><div class="provenance" id="provenance"></div></div></section>
<section id="patches"><h2>Download the instrumentation patches</h2><p class="sub">The Firefox patch records the compile, install, and discard events used in this report. The complete mailbox is embedded in this HTML, so the download also works offline.</p><div class="card"><a class="download" id="download-patches">Download patches (.patch)</a><p id="patch-provenance" class="provenance"></p><p>Apply the downloaded mailbox with <code>git am</code> in a Firefox checkout based on the revision above:</p><pre id="patch-command"></pre></div></section>
<footer>Draft dashboard · generated from the existing Fossil records · source: 0-1-baseline-cache-simulation-detail.json</footer>
</main>
<script id="data" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById("data").textContent);
const names=["speedometer3","jetstream3","tp6","manual"].filter(n=>D.workloads[n]), labels=names.map(n=>({speedometer3:"Speedometer 3",jetstream3:"JetStream 3",tp6:"tp6",manual:"Manual browsing"})[n]);
const kinds=["run","compile","install","discard","malformed","summary"];
const scopes=["first","same_runtime","same_process","cross_process"];
const scopeLabels=["First install","Same JSRuntime","Same process, other JSRuntime","Other process"];
const colors=["#bac9c3","#087f75","#6381ac","#cd694a"];
const $=id=>document.getElementById(id), w=n=>D.workloads[n], fmt=n=>Math.round(n).toLocaleString("en-US");
const pct=(a,b)=>b?(100*a/b).toFixed(1)+"%":"—";
const esc=s=>String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function opts(id){$(id).innerHTML=names.map((n,i)=>'<option value="'+n+'">'+labels[i]+"</option>").join("");}
function draw(id,paint){let el=$(id),r=el.getBoundingClientRect(),scale=devicePixelRatio||1;el.width=Math.round(r.width*scale);el.height=Math.round(r.height*scale);let c=el.getContext("2d");c.scale(scale,scale);paint(c,r.width,r.height);}
function grid(c,x,y,width,height,max){c.strokeStyle="#d6dfda";c.fillStyle="#657575";c.font="11px system-ui";for(let i=0;i<=4;i++){let yy=y+height-i*height/4;c.beginPath();c.moveTo(x,yy);c.lineTo(x+width,yy);c.stroke();c.fillText(fmt(i*max/4),2,yy+3);}}
function start(){
  $("meta").innerHTML='<div>RECORDINGS<b>'+names.length+'</b></div><div>EVENTS<b>'+fmt(names.reduce((sum,n)=>sum+w(n).events.length,0))+'</b></div><div>TRACE VERSION<b>1</b></div>';
  $("cards").innerHTML=names.map((n,i)=>{let d=w(n),c=d.candidate,repeat=c.installs-c.keys;return '<div class="card"><div class="label">'+labels[i]+'</div><div class="value">'+pct(repeat,c.installs)+'</div><div>'+fmt(repeat)+' repeated of '+fmt(c.installs)+' eligible installs</div><p class="small">'+fmt(c.keys)+' exact keys</p><div class="small">Median compile '+(d.distributions.candidate_compile_us.median?.toFixed(1)??"—")+' µs · median entry '+(d.distributions.candidate_cache_bytes.count?fmt(d.distributions.candidate_cache_bytes.median):"—")+' B</div>'+(d.manifest.description?'<p class=small>'+esc(d.manifest.description)+'</p>':'')+'</div>';}).join("");
  if(w("speedometer3")){
  $("overview-note").textContent="Speedometer 3 has strong exact-key recurrence, but its 4 MiB replay retains only "+fmt(w("speedometer3").cache_models["4mib"].hits)+" repeats. At 8 MiB this trace reaches the unlimited-cache ceiling. These are simulated reuse counts, not measured speedups; an install follows compilation and final linking.";
  }else{
    $("overview-note").textContent="These percentages count repeated candidate keys among completed installations. Cache capacity and the modeled body identity determine how many become hypothetical hits.";
  }
  $("recurrence-tabs").innerHTML=[["guest","Guest"],["self_hosted","Self-hosted"],["system","System"]].map(([kind,label])=>'<button type="button" data-kind="'+kind+'">'+label+'</button>').join("");
  $("recurrence-tabs").onclick=e=>{if(e.target.dataset.kind){recurrenceKind=e.target.dataset.kind;showRecurrence();}};
  $("provenance-table").innerHTML="<thead><tr><th>Workload</th><th>Code</th><th class=num>Installs</th><th class=num>Exact repeats</th><th class=num>Keys in multiple PIDs</th><th class=num>Other-PID repeat installs</th><th class=num>Relaxed cross-PID keys</th></tr></thead><tbody>"+names.flatMap((n,i)=>["guest","self_hosted","system"].filter(p=>w(n).provenance_summary[p]).map(p=>{let r=w(n).provenance_summary[p];return "<tr><td>"+labels[i]+"</td><td>"+p.replaceAll("_"," ")+"</td><td class=num>"+fmt(r.installs)+"</td><td class=num>"+fmt(r.repeat_installs)+"</td><td class=num>"+fmt(r.cross_process_keys)+"</td><td class=num>"+fmt(r.cross_process_repeats)+"</td><td class=num>"+(r.fingerprinted_installs?fmt(r.relaxed_cross_process_keys):"—")+"</td></tr>";})).join("")+"</tbody>";
  $("cross-process-note").textContent="The table checks whether candidate keys occur in multiple recorded PIDs. Self-hosted matches use bytecode and key metadata when source text is unavailable. The guest curve excludes self-hosted code. Relaxed cross-PID keys omit filenames and source offsets; this is a diagnostic identity. The original benchmark recordings placed almost all guest code in one content process. Manual browsing can exercise other process patterns, depending on the sites visited.";
  ["distribution-workload","source-workload","timeline-workload","event-workload"].forEach(opts);
  $("capacity-tabs").innerHTML=names.map((n,i)=>'<button data-name="'+n+'">'+labels[i]+"</button>").join("");
  $("capacity-tabs").onclick=e=>{if(e.target.dataset.name){capacity=e.target.dataset.name;showCapacity();}};
  $("size-model").onchange=showCapacity;
  $("distribution-workload").onchange=showDistribution;$("distribution-measure").onchange=showDistribution;
  $("source-workload").onchange=showSources;$("timeline-workload").onchange=showTimeline;
  ["event-workload","event-kind","event-scope","event-search"].forEach(id=>$(id).addEventListener(id==="event-search"?"input":"change",()=>{page=0;filterEvents();}));
  $("prev").onclick=()=>{page=Math.max(0,page-1);showEvents();};$("next").onclick=()=>{page++;showEvents();};
  $("method-key").textContent=D.methodology.key;
  $("method-candidate").textContent=D.methodology.candidate+". System and self-hosted code are excluded.";
  $("method-cache").textContent=D.methodology.cache+".";
  $("method-sizes").textContent=D.methodology.size_models+".";
  $("method-timing").textContent=D.methodology.timing+". These sums are not end-to-end speedup estimates.";
  $("method-limits").textContent=D.methodology.limits;
  $("provenance").innerHTML=names.map((n,i)=>{let d=w(n);return "<p><b>"+labels[i]+"</b> · "+esc(d.record_id)+" · Firefox "+(d.firefox_revisions.map(r=>esc(r)).join(", ")||"unknown")+" · Fossil "+esc(d.manifest.git.commit)+" · "+fmt(d.events.length)+" events · "+fmt(d.event_links.compiled_installs)+" linked compiles · "+fmt(d.event_links.matched_discards)+" matched discards</p>";}).join("");
  let bundle=D.patches,download=$("download-patches");
  download.href=URL.createObjectURL(new Blob([bundle.mbox],{type:"text/plain;charset=utf-8"}));
  download.download=bundle.filename;
  $("patch-provenance").textContent=bundle.repository+" · Base revision: "+bundle.base_revision+" · Instrumentation commits: "+bundle.commits.join(", ");
  $("patch-command").textContent="git am "+bundle.filename;
  showRecurrence();showCapacity();showDistribution();showSources();showTimeline();filterEvents();
  window.addEventListener("resize",()=>{capacityChart();distributionChart();showTimeline();});
}
let recurrenceKind="guest";
function showRecurrence(){
  document.querySelectorAll("#recurrence-tabs button").forEach(b=>{let selected=b.dataset.kind===recurrenceKind;b.classList.toggle("active",selected);b.setAttribute("aria-pressed",selected);});
  $("stacks").innerHTML=names.map((n,i)=>{let r=w(n).recurrence_by_provenance[recurrenceKind],total=scopes.reduce((sum,s)=>sum+r[s],0),repeats=total-r.first;return '<div class="stack-row"><b>'+labels[i]+'</b><div class="stack">'+scopes.map((s,j)=>'<div title="'+scopeLabels[j]+': '+fmt(r[s])+' installs ('+pct(r[s],total)+')" style="width:'+100*r[s]/(total||1)+'%;background:'+colors[j]+'"></div>').join("")+'</div><b class="num" title="'+fmt(repeats)+' repeats of '+fmt(total)+' installs">'+pct(repeats,total)+'</b></div>';}).join("");
  if(!w("speedometer3")){$("recurrence-note").textContent="Each repeat is compared with the most recent earlier occurrence of its candidate key. Matching runtime addresses do not imply the same script instance.";return;}
  let p=w("speedometer3").same_runtime_script_pointers[recurrenceKind],same=p.same_pointer,changed=p.different_pointer;
  let ten=w("speedometer3").ten_install_pattern;
  $("recurrence-note").textContent="Speedometer 3: "+fmt(changed)+" of "+fmt(changed+same)+" same-JSRuntime repeats have a different recorded JSScript address. "+fmt(same)+" retain the address; "+fmt(p.same_pointer_after_discard_and_compile)+" of those have a matched discard and a new compile. Addresses may be reused. "+(recurrenceKind==="guest"?fmt(ten.keys)+" guest keys were installed exactly ten times; "+fmt(ten.distinct_script_addresses)+" of those use ten distinct recorded script addresses. This is consistent with repeated benchmark passes creating fresh scripts in one JSRuntime. Guest counts require a source fingerprint and match the cache simulation population.":recurrenceKind==="self_hosted"?"Self-hosted source text was unavailable, so matches rely on bytecode and metadata.":"System counts include installs without a source fingerprint.");
}
let capacity=names[0];
function showCapacity(){let d=w(capacity),total=d.candidate.installs,model=$("size-model").value,curve=d.capacity_curve[model],ceiling=curve.at(-1).hits;
  document.querySelectorAll("#capacity-tabs button").forEach(b=>b.classList.toggle("active",b.dataset.name===capacity));
  let totalCompile=0,repeatCompile=0,missing=0,missingRepeats=0;
  for(let e of d.events){
    if(e[1]!==2||e[3]===null)continue;
    if(e[4]===null){missing++;if(e[6]!==0)missingRepeats++;continue;}
    totalCompile+=e[4];
    if(e[6]!==0)repeatCompile+=e[4];
  }
  const ms=us=>(us/1000).toLocaleString("en-US",{minimumFractionDigits:1,maximumFractionDigits:1});
  $("capacity-timing").textContent="Recorded eligible compilation: "+ms(totalCompile)+" ms total; "+ms(repeatCompile)+" ms on repeated keys ("+pct(repeatCompile,totalCompile)+"). Repeated-key time is the potential saving if compatible bodies are always ready and retained.";
  $("capacity-timing-coverage").textContent=missing?fmt(missing)+" eligible installations lack compile timing, including "+fmt(missingRepeats)+" repeats. Missing durations are excluded from the sums.":"Every eligible installation has a recorded compile duration.";
  let tableRows=curve.filter(r=>[1,4,8,12,16,32].includes(r.capacity_bytes/1048576));
  $("capacity-table").innerHTML="<thead><tr><th>Capacity</th><th class=num>Hit rate</th><th class=num>Compile avoided</th><th class=num>Share of total</th></tr></thead><tbody>"+tableRows.map(r=>"<tr><td>"+(r.capacity_bytes/1048576)+" MiB</td><td class=num>"+pct(r.hits,total)+"</td><td class=num>"+ms(r.hit_compile_us)+" ms</td><td class=num>"+pct(r.hit_compile_us,totalCompile)+"</td></tr>").join("")+"</tbody>";
  let first=curve.find(r=>r.hits===ceiling),footprint=d.unique_footprint_bytes[model]/1048576;
  let mechanism=capacity==="speedometer3"&&model==="code_plus_metadata"?" At 6.5 MiB, the LRU evicts "+fmt(curve.find(r=>r.capacity_bytes===6.5*1048576).evictions)+" entries; at 7 MiB, "+fmt(curve.find(r=>r.capacity_bytes===7*1048576).evictions)+". No entry is individually oversized at either capacity. Repeated passes through a corpus larger than the smaller cache cause churn.":capacity==="tp6"&&model==="code_plus_metadata"?" The 12 MiB dip is an LRU admission effect: a roughly 11.3 MiB entry becomes eligible, evicts many smaller entries, and has only two repeat installs.":"";
  $("capacity-note").textContent="First sampled capacity reaching this model's maximum of "+fmt(ceiling)+" hits: "+(first.capacity_bytes/1048576).toFixed(1)+" MiB. Sum of first-entry sizes: "+footprint.toFixed(2)+" MiB. "+fmt(d.candidate.variable_size_repeats)+" repeats belong to keys with varying recorded size. This is the retained cache inventory; it is different from peak concurrently live Baseline code. The sampled boundary is not an exact minimum, and no model is measured RSS."+mechanism;
  capacityChart();
}
function capacityChart(){let d=w(capacity),selected=$("size-model").value,total=d.candidate.installs,modes=["instructions","allocated_code","code_plus_metadata","code_plus_metadata_size_split"],palette=["#6381ac","#b38a3b","#087f75","#cd694a"];
  draw("capacity-chart",(c,width,height)=>{let x=45,y=15,cw=width-60,ch=height-45,peak=Math.max(...modes.map(m=>d.capacity_curve[m].at(-1).hits)),limit=Math.max(5,Math.ceil(100*peak/(total||1)/5)*5);grid(c,x,y,cw,ch,limit);
    modes.forEach((m,j)=>{let rows=d.capacity_curve[m].filter(r=>r.capacity_bytes<=16*1048576);c.strokeStyle=palette[j];c.globalAlpha=m===selected?1:.4;c.lineWidth=m===selected?3:1.5;c.beginPath();rows.forEach((r,i)=>{let xx=x+(r.capacity_bytes/1048576-1)/15*cw,yy=y+ch-(100*r.hits/(total||1))/limit*ch;if(i)c.lineTo(xx,yy);else c.moveTo(xx,yy);});c.stroke();rows.forEach(r=>{let xx=x+(r.capacity_bytes/1048576-1)/15*cw,yy=y+ch-(100*r.hits/(total||1))/limit*ch;c.fillStyle=palette[j];c.beginPath();c.arc(xx,yy,m===selected?2.5:1.5,0,Math.PI*2);c.fill();});});c.globalAlpha=1;c.fillStyle="#657575";c.font="11px system-ui";c.fillText("1 MiB",x,y+ch+18);c.fillText("8 MiB",x+cw*.47,y+ch+18);c.fillText("16 MiB",x+cw-39,y+ch+18);});
}
let distribution=[];
function values(d,measure){if(measure==="compile")return d.events.filter(e=>e[1]===2&&e[3]!==null&&e[4]!==null).map(e=>e[4]);if(measure==="size")return d.events.filter(e=>e[1]===2&&e[3]!==null).map(e=>e[5]);let out=[],prior=new Map();for(let e of d.events){if(e[1]!==2||e[3]===null)continue;let p=prior.get(e[3]);if(p!==undefined)out.push((e[0]-p)/1000);prior.set(e[3],e[0]);}return out;}
function showDistribution(){let d=w($("distribution-workload").value),m=$("distribution-measure").value;distribution=values(d,m);let q=d.distributions[({compile:"candidate_compile_us",size:"candidate_cache_bytes",gap:"recurrence_gap_us"})[m]],factor=m==="gap"?0.001:1;
  if(!q.count){$("distribution-note").textContent="No eligible observations for this measure.";$("distribution-table").innerHTML="<tbody><tr><td>No data</td></tr></tbody>";draw("distribution-chart",()=>{});return;}
  $("distribution-note").textContent=m==="gap"?"Recurrence gap is wall-clock time between consecutive installs of the same candidate key. It is not compilation time, install-to-discard lifetime, or idle time for an individual JSScript; page activity may occur between the two installs.":"Log-spaced bins show the observed distribution; zero values are included in the first bin.";
  $("distribution-table").innerHTML="<thead><tr><th>Statistic</th><th class=num>"+({compile:"µs",size:"B",gap:"ms"})[m]+"</th></tr></thead><tbody>"+[["Count",q.count],["Min",q.min*factor],["P25",q.p25*factor],["Median",q.median*factor],["P75",q.p75*factor],["P90",q.p90*factor],["P99",q.p99*factor],["Max",q.max*factor],["Mean",q.mean*factor]].map(([k,v])=>"<tr><td>"+k+"</td><td class=num>"+Number(v).toLocaleString("en-US",{maximumFractionDigits:2})+"</td></tr>").join("")+"</tbody>";distributionChart();}
function distributionChart(){if(!distribution.length)return;let max=distribution.reduce((a,b)=>Math.max(a,b),0),bins=28,counts=Array(bins).fill(0),bound=Math.log1p(max)||1;for(let v of distribution)counts[Math.min(bins-1,Math.floor(Math.log1p(v)/bound*bins))]++;draw("distribution-chart",(c,width,height)=>{let x=45,y=15,cw=width-60,ch=height-42,top=Math.max(...counts);grid(c,x,y,cw,ch,Math.ceil(top/100)*100);counts.forEach((n,i)=>{c.fillStyle=i<16?"#087f75":"#cd694a";c.fillRect(x+i*cw/bins,y+ch-n/top*ch,cw/bins-2,n/top*ch);});c.fillStyle="#657575";c.font="11px system-ui";c.fillText("0",x,y+ch+17);c.fillText("log scale",x+cw/2-20,y+ch+17);c.fillText(fmt(max),x+cw-35,y+ch+17);});}
function showSources(){let top=w($("source-workload").value).top_sources,max=top[0]?.repeats||1;$("source-table").innerHTML="<thead><tr><th>Source</th><th class=num>Installs</th><th class=num>Repeats</th><th>Concentration</th></tr></thead><tbody>"+top.slice(0,15).map(r=>'<tr><td class=source>'+esc(r.filename)+'</td><td class=num>'+fmt(r.installs)+'</td><td class=num>'+fmt(r.repeats)+'</td><td><div class=bar><span style="width:'+100*r.repeats/max+'%"></span></div></td></tr>').join("")+"</tbody>";}
function showTimeline(){let d=w($("timeline-workload").value),bins=d.timeline;$("timeline-note").textContent="Gray: first installs. Teal: repeats. The first eligible install was "+(d.timeline_origin_us/1e6).toFixed(1)+" s after runner start; earlier setup is omitted from this view.";draw("timeline-chart",(c,width,height)=>{let x=45,y=15,cw=width-60,ch=height-42,max=Math.max(1,...bins.map(b=>b[1])),last=bins.at(-1)?.[0]||1;grid(c,x,y,cw,ch,Math.ceil(max/100)*100);for(let [s,total,repeats] of bins){let bx=x+s/(last+1)*cw,bw=Math.max(1,cw/(last+1)-.3);c.fillStyle="#bac9c3";c.fillRect(bx,y+ch-total/max*ch,bw,total/max*ch);c.fillStyle="#087f75";c.fillRect(bx,y+ch-repeats/max*ch,bw,repeats/max*ch);}c.fillStyle="#657575";c.font="11px system-ui";c.fillText("0 s",x,y+ch+17);c.fillText(last+" s",x+cw-35,y+ch+17);});}
let page=0,filtered=[];
function filterEvents(){let d=w($("event-workload").value),kind=$("event-kind").value,scope=$("event-scope").value,term=$("event-search").value.toLowerCase().trim();filtered=[];d.events.forEach((e,i)=>{if(!["compile","install","discard"].includes(kinds[e[1]]))return;if(kind!=="all"&&kinds[e[1]]!==kind)return;if(scope!=="all"&&scopes[e[6]]!==scope)return;if(term&&!(e[7]===null?"":d.sources[e[7]]).toLowerCase().includes(term))return;filtered.push(i);});showEvents();}
function showEvents(){let d=w($("event-workload").value),pages=Math.max(1,Math.ceil(filtered.length/50));page=Math.min(page,pages-1);$("event-count").textContent=fmt(filtered.length)+" matching events";$("page").textContent="Page "+(page+1)+" of "+pages;$("prev").disabled=page===0;$("next").disabled=page===pages-1;
  $("event-rows").innerHTML=filtered.slice(page*50,(page+1)*50).map(i=>{let e=d.events[i],source=e[7]===null?"":d.sources[e[7]];return '<tr data-i="'+i+'"><td class=num>'+fmt(i)+'</td><td class=num>'+(e[0]===null?"—":(e[0]/1e6).toFixed(3)+" s")+'</td><td>'+kinds[e[1]]+'</td><td class=num>'+(e[2]??"—")+'</td><td class=num>'+(e[3]??"—")+'</td><td class=num>'+(e[4]===null?"—":fmt(e[4])+" µs")+'</td><td class=num>'+(e[5]===null?"—":fmt(e[5])+" B")+'</td><td>'+(e[6]===null?"—":scopeLabels[e[6]])+'</td><td class=source>'+esc(source)+'</td></tr>';}).join("");
  $("event-rows").onclick=ev=>{let row=ev.target.closest("tr[data-i]");if(!row)return;document.querySelectorAll("#event-rows tr").forEach(r=>r.classList.toggle("selected",r===row));let i=Number(row.dataset.i),e=d.events[i],key=e[3]===null?null:d.keys[e[3]];$("event-detail").textContent=JSON.stringify({event_index:i,elapsed_us:e[0],event:kinds[e[1]],pid:e[2],key_id:e[3],compile_us:e[4],cache_bytes:e[5],recurrence_scope:scopes[e[6]]??null,filename:e[7]===null?null:d.sources[e[7]],link_us:e[8],lifetime_us:e[9],key_summary:key&&{installs:key[1],cache_bytes_min:key[2],cache_bytes_max:key[3],runtime_count:key[4]}},null,2);};}
start();
</script>
</body>
</html>
'''


if __name__ == "__main__":
    main()

#import "lib/figures.typ": rit-access, aot-image-layout, cacheir-sharing-example, code-lowering-panel, image-relocation-scaffold, string-int32-cacheir
#import "lib/figure-placement.typ": figure-body, figure-placement, figure-scope
#import "lib/tables.typ": table-from-json
#import "lib/coverage-table.typ": coverage-table
#import "lib/execution-configurations-table.typ": execution-configurations-table
#import "lib/aot-installation-cost-table.typ": aot-installation-cost-table
#import "lib/inter-workload-reuse-table.typ": inter-workload-reuse-table
#import "lib/runtime-dependencies-table.typ": runtime-dependencies-table
#import "constants.typ": *
#import "@preview/algo:0.3.6": code

#set page(
  paper: "us-letter",
  margin: (
    top: 2cm, bottom: 1.5cm,
    left: 1.9cm, right: 1.9cm
  ),
  columns: 2,
  numbering: "1",
)
#set text(
  font: ("Times New Roman", "TeX Gyre Termes"),
  size: 10pt,
  lang: "en"
)
#set par(
  justify: true,
  first-line-indent: 1em,
  spacing: 0.4em,
  leading: 0.5em,
)
#show figure.caption: set text(size: 8.5pt)

#let TODO(body) = box(
  stroke: 1.5pt + red,
  inset: 4pt,
  radius: 2pt,
  fill: rgb(255, 230, 230),
  text(fill: red, weight: "bold", size: 8pt)[TODO: #body]
)

#let NOTE(body) = box(
  stroke: 1.5pt + rgb(180, 140, 0),
  inset: 4pt,
  radius: 2pt,
  fill: rgb(255, 248, 220),
  text(fill: rgb(100, 80, 0), weight: "bold", size: 8pt)[NOTE: #body]
)

#let fig(path, caption, width: 100%, height: 100%, placement: top, scope: "column", at: none) = figure(
  figure-body(at, image(path, width: width)),
  caption: caption,
  placement: figure-placement(at, placement),
  scope: figure-scope(at, scope),
)

#let section(title) = {
  show heading: set text(size: 10pt, weight: "regular")
  show heading: set align(center)
  heading(
    level: 1,
    numbering: (..numbers) => numbering("I.", numbers.pos().last()),
    upper(title),
  )
}

#let subsection(title) = {
  show heading: set text(size: 10pt, style: "italic", weight: "regular")
  heading(
    level: 2,
    numbering: (..numbers) => numbering("A.", numbers.pos().last()),
    title,
  )
}

#place(
  top,
  scope: "parent",
  float: true,
  block(width: 100%)[
    #align(center)[
      #text(size: 17pt, weight: "bold")[
        AmberMonkey: Decoupling JIT Code Generation
        #linebreak()
        from JavaScript Execution
      ]
    ]
    #v(0.8em)
    #grid(
      columns: (1fr, 1fr, 1fr),
      align(center)[
        *DRAFT*  \
        #link("mailto:draft@draft.ca") \
        University of Alberta \
        Edmonton, Canada
      ],
      align(center)[
        *DRAFT*  \
        #link("mailto:draft@draft.ca") \
        University of Alberta \
        Edmonton, Canada
      ],
      align(center)[
        *DRAFT*  \
        #link("mailto:draft@draft.ca") \
        University of Alberta \
        Edmonton, Canada
      ],
    )
    #v(1em)
  ]
)

#pad(x: 0.2em)[
#text(weight: "medium", size: 10pt)[

#NOTE("---------------------------------------------------------------------")
#NOTE("Draft will be moved to an OverLeaf link as of August 31st. Some edits are offline and this draft is a few days out of date currently.")
#NOTE("---------------------------------------------------------------------")

  
$space$

Restricted execution prevents guest programs from triggering just-in-time
(JIT) compilation, reducing a JavaScript engine's attack surface at
substantial performance cost. Moving JIT code generation into a trusted
ahead-of-time (AOT) build can recover lost performance, however, dynamic
browser workloads create two constraints. First, any AOT compiled artifact
must generalize to unseen workloads to justify it's binary cost. Second,
unlike dedicated AOT compilers, existing JIT code generators are not
designed for cross-process reuse.

This paper presents AmberMonkey, an AOT code-generation model extended from
SpiderMonkey. AmberMonkey identifies inline-cache (IC) stubs as an effective
source of performance recovery: their compiled bodies recur across workloads
despite specializing on runtime behavior. AmberMonkey operates beneath
existing JIT interfaces, turning regular JIT generation into AOT code
transparently. Runtime dependencies are routed through a side table,
imposing a indirection to gain a reusable form.

AmberMonkey uses #ic-stub-count IC bodies (#ic-stub-bytes) collected from
common websites to serve #sp3-ic-hit-rate of IC requests on Speedometer 3.1
and #js3-ic-hit-rate on JetStream 3.0. Combined with #self-hosted-fn-count
Baseline compiled self-hosted functions, Speedometer 3.1 throughput is
improved by #sp3-aot-speedup under restricted execution, reaching
#sp3-aot-default-fraction of default tiered-JIT throughput.

]
]


#section[Introduction]
#linebreak() 

$space$ Modern JavaScript engines rely on just-in-time (JIT) compilation to
execute guest programs efficiently. However, mapping attacker-controlled
JavaScript to native instructions forms a security risk. Despite years of
mitigation effort, JIT compilers remain a source of vulnerabilities
@gross2026state. Restricted execution modes, such as V8's JITless mode,
close this path by preventing guest programs from triggering JIT
compilation. When V8 introduced JITless mode, however, Speedometer 2
throughput fell by 40% @gruber2019jitless. A restricted engine must recover
native execution without restoring guest-directed code generation.

Ahead-of-time (AOT) compilation appears to provide this native execution,
but it normally applies to a fixed application. A browser does not know
which JavaScript future websites will deliver. It therefore cannot compile
those applications when the engine is built. The engine can, however,
pre-compile native code that recurs across applications. This narrowed
use-case for AOT compilation shifts the question towards identifying JIT
code with a high cross-workload recurrence.

Inline caches (ICs) accelerate common dynamic operations and are a primary
target for recovering performance under restricted execution. Interpreter ICs
show that inline caching can operate without run-time code generation by
selecting from handlers generated with the engine. Some JIT compilers instead
generate dedicated native IC stubs on demand, specializing them to cases
observed during execution. Restricted execution prevents this form of
specialization. Providing the resulting stubs ahead of time initially appears
infeasible because future applications can introduce an unbounded set of IC
sites, observed types, and run-time identities.

An unbounded set of IC specializations does not necessarily require an
unbounded set of executable bodies. Two design properties allow specializations
from different sites to share code. First, a structured intermediate
representation composes specialized operations from a recurring set of
primitives. Second, code–data separation keeps site-specific values outside the
executable body. Together, these properties allow a fixed AOT corpus to provide
many of the IC stubs otherwise generated at run time.

A reusable IC corpus addresses the availability of specialized code, but it
does not make that code independent of the runtime that generated it.
Ordinary JIT generators assume that generation and execution occur in the
same runtime. Their output can therefore contain concrete addresses of
helper routines, generated code, and mutable engine state. Some of these
dependencies express the body's intended specialization and must remain
unchanged. Others merely encode one runtime's representation of equivalent
engine services. These dependencies constitute _semantic coupling_ and
_incidental coupling_, respectively. Section IV develops these definitions.
Reusable AOT code must preserve semantic coupling while removing incidental
coupling.

This distinction forms the basis of _AmberMonkey_, an AOT code-generation model
that performs this transformation beneath existing JIT code-generation
interfaces. During a trusted build, AmberMonkey translates external addresses
emitted by ordinary generators into stable references. A per-runtime _Runtime
Indirection Table_ (RIT) supplies targets that differ across runtimes or cannot
be named as linkable symbols. Each runtime can therefore provide equivalent
engine state without modifying the shared instructions. AmberMonkey uses the
same generators for conventional JIT compilation and AOT image construction,
avoiding a separate AOT backend.

An implementation in SpiderMonkey applies AmberMonkey to Baseline functions,
IC bodies, and deterministic Baseline Interpreter code. The model is not
specific to SpiderMonkey: it applies to runtimes that separate generated
instructions from specialization data and can identify the external
dependencies of their generated code. The contributions of this paper are the
following:

#linebreak()

1. A structured IC representation and code–data separation allow a finite,
   high-coverage AOT corpus to serve run-time-generated ICs across sites and
   workloads.

   #linebreak()

2. AmberMonkey removes incidental runtime coupling beneath SpiderMonkey's
   existing JIT interfaces. Linker-resolved symbols and a per-runtime RIT
   preserve immutable AOT instructions without AOT-specific changes to
   higher-level generators.

   #linebreak()

3. The evaluation measures cross-workload generalization, restricted-execution
   performance, and runtime-independence costs. A corpus of
   #ic-stub-count IC bodies collected from page loads of
   #tp6-train-site-count websites serves #sp3-ic-hit-rate of attachment
   requests on Speedometer 3.1 and #js3-ic-hit-rate on JetStream 3.0.
   AmberMonkey improves Speedometer 3.1 throughput by #sp3-aot-speedup over
   bytecode-only execution. Additional experiments quantify runtime-indirection
   overhead, binary size, and per-content-process engine proportional set size
   (PSS).


   #linebreak()
#section[The Complexity of Optimizing JavaScript]

#linebreak()

$space$ This section defines the security considerations that shape
AmberMonkey's restricted-execution model. While removing guest-triggered JIT
compilation limits the scope of directly controlled attacker inputs, AOT
code can still contain pre-existing bugs. AmberMonkey therefore reuses
production Baseline code
generators during a trusted build instead of introducing another interpreter
or AOT compiler backend. This choice avoids another implementation of
JavaScript semantics, but it does not remove defects from the reused generators
or captured code.


#subsection[Guest-Triggered JIT Compilation]

$space$ Guest-triggered just-in-time (JIT) compilation exposes a direct path from
attacker-controlled inputs to native instructions. An attacker can shape
both the bytecode being compiled and the run-time profiles that drive
speculative optimization. A missed side effect or invalid type assumption
can cause the compiler to emit instructions that violate the engine's
memory-safety invariants. Notably, implementing the compiler in a
memory-safe language does not prevent these logic errors, as generated
instructions elide the constraints of the high-level language entirely.

Automated bug finding can expose browser vulnerabilities at scale, but it has
not exhausted the JIT attack surface. Mozilla reported that an early evaluation
of Anthropic's Mythos Preview identified 271 vulnerabilities fixed in Firefox
150 and presented this result as shifting the balance against zero-day
exploits @holley2026zerodays. Several months later, Nebula Security disclosed
CVE-2026-10702, a high-severity SpiderMonkey JIT miscompilation that enabled
arbitrary code execution @nebula2026ionstack. JIT security therefore remains
an active problem even after large automated audits.

#subsection[Semantic Complexity Without JIT Compilation]

$space$ Removing JIT compilation narrows the attack surface but does not remove
the semantic complexity of language execution. Both compilers and interpreters
must implement type, control-flow, and memory-management semantics correctly.
Microsoft's DrumBrake WebAssembly interpreter illustrates this engineering
risk: researchers reported 23 remote-code-execution vulnerabilities involving
type confusion, reference-stack indexing, missing garbage-collection barriers,
and incorrect control-flow handling @wang2026en[?1;2;4chancedinsecurity. Although
DrumBrake executes WebAssembly rather than JavaScript, the result demonstrates
the narrower point that replacing compilation with interpretation shifts,
rather than eliminates, implementation risk.

Together, these observations impose two design constraints. First, AmberMonkey
admits only artifacts generated during a trusted build. Guest execution may
select and parameterize an existing artifact but cannot generate new
instructions. Second, AmberMonkey reuses production Baseline generators
rather than adding another interpreter or AOT compiler backend. A 2026
analysis of known exploitable V8 bugs found that Baseline JITs were rarely
the source of vulnerabilities, whereas JITs collectively accounted for
roughly half @gross2026state. This evidence supports limiting our prototype
to the less speculative Baseline tier rather than capturing optimizing-tier
artifacts. These choices remove guest-directed code generation and avoid
another implementation of JavaScript semantics; they do not remove defects
from the reused generators or captured artifacts.


#subsection[Restricted Execution]

$space$ AmberMonkey's restricted execution prevents all guest-controlled JIT
compilation, including Baseline-function, inline-cache-stub, optimizing-tier,
and regular-expression compilation. Two remaining implementation gaps prevent
a pure static-executable-memory mode, as exemplified by V8 Jitless
@gruber2019jitless. First, SpiderMonkey still generates deterministic
trampolines during initialization. Generating them ahead of time is feasible
but requires nontrivial engineering outside this work's scope. It would
eliminate redundant trampoline compilation across runtimes and reduce memory
consumption, but is unlikely to measurably affect throughput. Second,
SpiderMonkey lacks a WebAssembly interpreter, so JetStream 3.0 retains
WebAssembly compilation. Section VII therefore qualifies this imperfect
comparison with V8 Jitless. Neither gap prevents AmberMonkey from demonstrating
the efficacy of its AOT design.

#linebreak()

#section[Structured Inline Caching Forms a Bounded AOT Corpus]

#linebreak()

$space$ A finite, high-coverage set of IC stubs enables native
specializations normally produced through run-time code generation to be
provided statically. This section develops that result by characterizing IC
designs and contrasting what we call fixed-handler ICs with run-time-generated
ICs. Fixed-handler ICs specialize interpreted execution without generating
native code at run time, whereas run-time-generated ICs can compose dedicated
stub bodies for observed cases. The former naturally bounds executable code,
whereas the latter supports specializations for which the engine did not
enumerate dedicated handlers. Measurements across unrelated workloads show that
many IC sites request the same set of stub bodies. AmberMonkey can therefore
reclaim almost all the performance of run-time inline caching through lookups
in an AOT corpus, falling back to the interpreter when that corpus lacks a body.

#subsection[Inline Caching]

$space$ At a high level, inline caching avoids repeated generic handling by
caching guarded fast paths for values observed at a program location. We
call one such path an _IC specialization_. Its guards check conditions such
as operand types, receiver shapes, or callees before executing a specialized
operation. If a guard fails, execution continues to another specialization or
a generic fallback. Deutsch and Schiffman introduced this technique for Smalltalk
method dispatch, and polymorphic inline caches later allowed one site to
retain several specializations @deutsch1984smalltalk @holzle1991pic.

Interpreter ICs demonstrate that specialization can occur without generating
native code at run time. Brunthaler describes interpreters that update a
handler pointer or replace a generic bytecode with a pre-generated
specialized opcode @brunthaler2010quickening. This second approach, called
_quickening_, specializes the interpreted instruction while drawing from a
fixed executable set. 

// Modern JavaScript engines use ICs to specialize dynamic bytecode operations.
// The primary difference is between pre-generated handlers that execute
// common patterns of specialized operations and run-time-generated designs
// that produce dedicated native code for each specialization case.

#string-int32-cacheir(at: (3, top, left))

#subsection[Run-Time-Generated versus Fixed-Handler ICs]

$space$ IC designs differ in when they obtain executable code for a
specialization. A _fixed-handler_ IC selects from code generated when the
engine is built. A _run-time-generated_ IC generates code after observing an
operand case.

A fixed-handler design bounds its executable code when the engine is built.
Run-time observations select a handler and supply its site-specific data.
Even if a workload heavily exercises generic handlers, the engine does not
dynamically specialize the handler set to accommodate that workload. V8's
Ignition interpreter exemplifies this constraint. Ignition records IC
observations and handler selections in a feedback vector and executes
exclusively pre-generated
handlers @alle2018codecaching. This design is directly compatible with
restricted execution. Cases without a dedicated handler must use another
handler already present in the engine, potentially a more general one.

A run-time-generated design adds a fast path when an IC site observes a new
operand combination—for example, a property access with a new receiver type
and property offset. JavaScriptCore (JSC) and SpiderMonkey exemplify
run-time-generated designs. JSC generates native polymorphic stubs that
dispatch on the object structures observed at a site @henderson2023ic.
SpiderMonkey also generates native stubs but uses a high-level intermediate
form called CacheIR to describe IC-stub computations composed from a set of
primitive operations @demooij2023cacheir.

#cacheir-sharing-example(at: (3, top, right))

At first glance, a run-time-generated IC design appears incompatible with an
AOT model. A program may contain millions of IC sites, and each site may
specialize to private run-time data. Generating a separate body ahead of
time for every possible site and observation would not produce a bounded
corpus. We show that, in practice, two design properties constrain the set of
stub bodies compiled by a workload. First, a structured intermediate form
composes specializations from a fixed set of primitive operations. Second,
AmberMonkey's separation of code from data allows different sites to share
one body. The next two subsections show how CacheIR realizes these
properties.

#subsection[CacheIR Composition]

$space$ CacheIR represents an IC specialization as a sequence of primitive
operations. After the engine observes an operand case that can be specialized,
a CacheIR generator composes the guards, conversions, and operation needed for
its fast path. A CacheIR compiler then lowers the sequence into a native stub
body.
Generators reuse the same primitive operations across specializations
instead of defining each complete path as a dedicated handler.

String–integer subtraction provides a concrete example. As shown in
@fig-string-int32-cacheir, CacheIR composes four existing operations that
guard the string, convert it to an int32, guard the second operand, and
subtract the two integers. The CacheIR compiler lowers this sequence into
one dedicated native stub body. CacheIR is a language for constructing
specializations by composing common primitives. This composition allows
seemingly disparate specializations to share a canonical stub body.

#subsection[CacheIR Defines Shareable Stub Bodies]
// CacheIR further constrains the set of stub bodies by separating a
// specialization's operations from its site-specific values.

$space$ @fig-cacheir-sharing shows two property-access sites with different
receiver shapes and property offsets. Despite these differences, their
fixed-slot cases share a common stub body. `GetProp-A` is polymorphic. Although
the access `o1.x` is syntactically fixed, the object's shape and the offset of
property `x` vary at run time. Because an out-of-line dynamic-slot load and an
inline fixed-slot load are semantically distinct, CacheIR compiles distinct
stub bodies for them. By contrast, `GetProp-B` remains monomorphic at this
point. It has observed only one property-access case, in which `y` is stored in
a fixed slot under the layout defined by shape `S2`. Although its shape and
offset differ from those of `GetProp-A`'s fixed-slot access, the two cases can
share an IC stub. They can do so because CacheIR separates code from data.

Rather than embedding a shape directly in a guard or an offset directly in a
load operation, CacheIR accesses run-time data through parameters. Each node
in the `ICStubData` linked list stores the arguments supplied to a particular
stub. This separation allows the stub data for `GetProp-A` and `GetProp-B` to
parameterize the same fixed-slot stub body.

`ICStubData` also determines the control-flow destination when a stub guard
fails. In this sense, a stub's control flow is also parameterized, as
illustrated by the distinct paths from `GetProp-A` and `GetProp-B` through
their shared stub. The former jumps directly to the subsequent stub because
its data specify the next stub in the chain, whereas the latter proceeds to
the fallback stub. Dynamic IC-site data and stub bodies can therefore have a
many-to-one relationship. This property helps explain our empirical
observation that a finite corpus can serve held-out workloads with high coverage.

#subsection[Cross-Workload Reuse]

#fig(
  "lib/figures/3-3-corpus-growth.pdf",
  [Static and dynamic intersection with pooled tp6-Test as tp6-Train workloads
   are added in alphabetical order.],
  at: (4, top, left),
) <fig-interworkload-coverage>

$space$ We set up an experiment to provide empirical support for the claim
that CacheIR's design is conducive to a finite, high-coverage corpus. The
dataset contains #tp6-site-count websites from Mozilla's tp6 page-load
benchmark suite @mozilla2026tp6. Of these, #tp6-train-site-count websites
form _tp6-Train_, while the remaining #tp6-test-site-count websites form the
held-out _tp6-Test_ set. We quantify the generalization of JIT artifacts to
_tp6-Test_ using successively larger subsets of _tp6-Train_: first only the
first site, then the first two sites, and so on.

We consider two classes of JIT artifacts. The first consists of
CacheIR-compiled IC stubs. For comparison, the second consists of
Baseline-compiled function bodies. We use two metrics to quantify how IC stubs
and Baseline function bodies generalize across workloads. Treating each
workload as the set of artifacts it requests, _static intersection_ measures
recurrence, while _dynamic intersection_ weights shared artifacts by their
execution frequency in target $B$:

#linebreak()
$
  I_"static"(A, B) = frac(abs(A inter B), abs(A union B)), quad
  I_"dyn"(A arrow.r B) = frac(sum_(a in A inter B) "exec"_B(a), sum_(a in B) "exec"_B(a)).
$
#linebreak()

// _Dynamic intersection_ reports the fraction of artifact executions in target
// $B$ attributed to artifacts also observed in source $A$. Reversing the
// direction would weigh the shared artifacts according to their use in $A$.
// Each Baseline-function invocation and each attached IC-stub invocation
// contributes one execution. Fallback-stub execution does not contribute.

At point $k$, source $A$ is the union of the first $k$ tp6-Train workloads
and target $B$ is the pooled tp6-Test set. We order the training workloads
alphabetically. @fig-interworkload-coverage reports the cumulative results.
The first workload accounts for #inter-ic-dynamic-first of tp6-Test IC-stub
executions. All #inter-site-count workloads account for
#inter-ic-dynamic-final, while the final four add only
#inter-ic-dynamic-tail-gain percentage points. Complete Baseline functions
remain workload-specific: the full training union reaches
#inter-baseline-dynamic-final dynamic intersection. We therefore have
preliminary evidence that Inline Cache stubs generalize remarkably well to
unseen workloads.

#section[AmberMonkey Design]

#linebreak()

$space$ AmberMonkey converts ordinary output from existing Baseline generators
into artifacts that can execute across compatible runtimes. It preserves the
generators' interfaces while changing how their external references are
represented. Every external reference must remain relative to the artifact, be
resolved by the final native link, or use a runtime-stable slot in a
per-runtime _Runtime Indirection Table_ (RIT). AmberMonkey rejects an artifact
when none of these representations applies.

Each compatible runtime constructs the same RIT layout with its own addresses.
AOT artifacts access these entries at deterministic offsets without modifying
their shared instructions during ordinary execution. This section explains
where AmberMonkey intercepts generated references, how it selects their
representations, and how shared code locates the current runtime's table.

#subsection[Preserving Existing Generators]

$space$ AmberMonkey introduces AOT capture beneath SpiderMonkey's existing Baseline
code-generation interfaces. During a trusted build, SpiderMonkey produces
Baseline bodies, inline-cache bodies, and deterministic engine infrastructure
through their ordinary generators. This placement preserves the production engine's frame,
garbage-collection, exception-handling, stack-walking, and tiering contracts.

Capturing ordinary generator output also separates corpus selection from
artifact implementation. AmberMonkey can execute JavaScript available during a
trusted build and retain the Baseline artifacts requested by that workload.
Artifacts therefore need not be hand-authored for inclusion in the image. We
use this path to capture the #self-hosted-fn-count self-hosted functions in the
evaluated corpus.

V8's Embedded Builtins establish that generated engine routines can be made
immutable and process independent @gruber2018builtins. V8 provisions these
routines through a builtin-specific authoring path in which Torque-generated
C++ invokes the `CodeStubAssembler` and part of the TurboFan backend
@v8torque. AmberMonkey instead captures artifacts produced through the
ordinary Baseline interfaces, allowing corpus membership to follow observed
demand.

#subsection[Incidental Runtime Coupling]

$space$ The introduction distinguishes semantic from incidental coupling. Semantic
coupling limits reuse to executions compatible with an artifact's
specialization. Section III limits the corpus to artifacts whose lookup keys
recur across workloads and keeps site-specific inline-cache data outside shared
bodies. For example, an IC can specialize on a garbage-collected object
shape. Shape identity is runtime-local: an object with the same property layout
in another runtime still has a distinct `Shape`. AmberMonkey cannot translate
an embedded `Shape` pointer into equivalent runtime state and would reject such
an artifact. CacheIR avoids embedding this pointer by storing the expected shape
in site-private stub data, leaving only the generic guard instructions in the
shared body. This section addresses the remaining incidental coupling:
process-local representations of equivalent engine services or state.

Baseline generation embeds concrete addresses of runtime-specific state in
native instructions. Panel (a) of @lst-code-lowering shows a simplified
Baseline generator that obtains the current runtime's interrupt flag and passes
its address to `ImmPtr`.

During generation, `ImmPtr` converts the generating runtime's flag address
into an immediate machine-code operand. Copying the emitted instructions
into a separately initialized process preserves that numeric address, which
does not identify the destination runtime's flag. The generated check requires
the current runtime's flag, not the address assigned to that flag in the
generating process. Its semantic role is stable, but ordinary code generation
represents it with a process-local value. We call this _incidental runtime
coupling_.

#subsection[Resolving External Addresses]

$space$ We resolve each external address at the earliest stage that can identify its
correct target. In the simplest case, artifact-local branches use PC-relative
displacements that remain valid when the body moves. An external target
can use a native-linker relocation only when it denotes the same engine
definition for every runtime, the image-embedding translation unit can name
its symbol, and that symbol binds non-preemptibly in the final engine library.
The instruction must also admit a supported PC-relative relocation. The linker
then fixes the displacement between the image and the definition. Address-space
layout randomization may change their absolute addresses, but it does not
change this displacement.

All other supported external targets use fixed RIT slots. This category
includes addresses created during runtime or JIT initialization, values
supplied by the embedder, preemptible definitions, and definitions that the
image-embedding translation unit cannot name. JIT initialization populates
these slots after creating the runtime-specific state and generated code.
A target that cannot be linked directly or represented by a runtime-stable RIT
entry causes AmberMonkey to reject the artifact.
@tab-runtime-dependencies summarizes how AmberMonkey handles each reference
class.

#code-lowering-panel(placement: top)

#figure(
  runtime-dependencies-table(),
  caption: [Classification and treatment of embedded references in image-backed
    Baseline artifacts. Run-time-generated targets are deterministic engine
    infrastructure created during trusted initialization, not guest-compiled
    code.],
  placement: top,
  scope: "column",
) <tab-runtime-dependencies>

The RIT resembles an ELF global offset table (GOT). Both store absolute
addresses in private data while keeping position-independent text shareable
@tis1995elf. A conventional GOT names symbols that a linker or loader can
resolve. Its standard relocations cannot name per-runtime contexts, runtime
caches, or JIT-generated entry points. These values have no linkable symbols.
We assign each such role a stable slot, then give every runtime a RIT
with the same layout and its own addresses.

#subsection[Classifying Embedded References]

$space$ AmberMonkey classifies embedded references at the MacroAssembler boundary,
keeping AOT capture transparent to higher-level code generators. A finite
dependency table assigns a stable identifier to each supported engine target.
During capture, the active runtime maps intercepted pointer operands back to
these identifiers. Each identifier selects either a native-linker relocation
or a RIT access under the conditions above. An unrecognized pointer causes a
strict AOT capture to report the missing dependency and reject the artifact.
Baseline and IC generators can continue to issue ordinary MacroAssembler
operations without AOT-specific logic. @lst-code-lowering illustrates this
interception and the resulting RIT access.

An address qualifies for the table only if it remains fixed while its
runtime can execute AOT code. The address may differ across runtimes, and the
storage it names may remain mutable. For example, a RIT slot can hold the stable
address of a nursery cursor or profiler flag whose contents change during
execution. We call such an address _runtime-stable_.

Garbage-collected pointers require an additional lifetime guarantee. An
immutable artifact cannot trace a pointer or update it when its target moves.
AmberMonkey therefore admits such a pointer only when its target remains
nonmoving and live for every runtime that can execute the artifact. It rejects
pointers to movable or reclaimable cells.

#subsection[Accessing the RIT]

$space$ A shared artifact must locate the RIT without embedding a direct reference
to the table in its image. There are three possible solutions: thread-local storage, a pinned
register, and SpiderMonkey's existing frame layouts.

#linebreak()
_Thread-local storage (TLS)._ TLS can associate each executing thread with its
current `JSContext`, from which host code reaches runtime-specific pointers
through several nested structures. An AOT artifact could use the same path to
locate the RIT, but each access would require several dependent loads before
reaching a table entry. More importantly, directly generated TLS accesses
depend on offsets assigned for a particular process layout. Library load order
and TLS allocation order can change these offsets, so an access captured during
the trusted build may address the wrong TLS slot in another process.

#linebreak()
_Pinned register._ Keeping the RIT base in a dedicated general-purpose register
removes the frame load from every RIT access. V8 uses this approach for
isolate-relative accesses @gruber2018builtins. SpiderMonkey already reserves
registers for interpreter and IC state, and a register pinned across JIT tiers
must also be removed from the optimizing compiler's allocatable set. Optimized
code that does not access the RIT would therefore bear the resulting register
pressure. Limiting the contract to Baseline code instead requires tier
transitions to restore the base whenever control enters image-backed code.
Our x86-64 implementation therefore retains SpiderMonkey's existing register
contracts. AArch64's larger general-purpose register file may instead make
pinning practical, eliminating the frame load from every RIT access and
reducing indirection overhead.

#linebreak()
_Baseline and stub frames._ AmberMonkey stores the RIT base at a fixed offset
in the active frame, while each table entry remains at a deterministic slot
offset. Baseline bodies and the Baseline Interpreter load the RIT base from
this field in the active Baseline frame. IC stubs use their caller's frame
until a runtime call creates a stub frame, at which point AmberMonkey copies
the RIT base into the new frame. Shared code can therefore recover the base
from the active frame with one load. @fig-rit-access shows how each virtual
machine reaches its private RIT through the active frame while sharing the AOT
Baseline Interpreter.

#rit-access(placement: top)

Every path that creates or reconstructs an eligible frame initializes the RIT
field before shared code executes. Trampolines pass the base to
image-backed artifacts, while run-time-generated Baseline code, bailout,
on-stack replacement, and generator resumption initialize it when constructing
compatible frames. The design adds one machine word to each Baseline or
materialized stub frame. Resolving an address through the RIT requires two
dependent memory accesses: loading the RIT base from the active frame, then
loading the address from the selected slot. On x86-64, an indirect call or
jump incorporates the second access into the control-transfer instruction.

Ordinary SpiderMonkey generates a separate Baseline Interpreter for each
concurrent virtual machine, and each copy embeds addresses belonging to that
machine. AmberMonkey replaces these duplicated instruction bodies with a
single AOT Baseline Interpreter in the image. Each virtual machine retains its
own RIT and program stack, so runtime-specific state remains private while the
executable artifact is shared.

#section[Implementation]

#linebreak()

$space$ AmberMonkey integrates AOT artifacts into SpiderMonkey while preserving
its existing code generators and JIT interfaces. The implementation captures
native instructions and the metadata needed to reconstruct runtime objects for
Baseline bodies and CacheIR stubs, then packages both into the engine library.
At run time,
AmberMonkey represents image-backed instructions with existing JIT types and
adapts garbage collection, debugging, and profiling to their static ownership.
Two additional techniques use native-linker relocations and mirrored state to
eliminate selected RIT accesses. The following subsections describe these
mechanisms and the scope of the x86-64 prototype.

#subsection[Image Construction]

$space$ AmberMonkey constructs the AOT image through a bootstrap build and a final
relink. The bootstrap engine contains an empty valid image and executes the
self-hosted library and tp6-Train while the ordinary code generators capture
selected artifacts. The AOT image builder serializes these artifacts for the
final build, which recompiles the image-embedding shim and relinks the engine
library. The bootstrap and final builds use the same object tree and target
configuration.

@fig-aot-image-layout shows the packed layout, in which a flat directory maps
each artifact kind and lookup key to its metadata and optional instruction
ranges.
The image places 16-byte-aligned instruction bodies within a page-aligned code
region and stores image-wide configuration in a metadata-only record.

#aot-image-layout(placement: top)

A declarative YAML schema defines the wire format and generates C++ structures,
encoders, decoders, and compile-time layout checks. The image header stores an
explicit format version and a fingerprint that identifies the packed corpus.
The loader rejects incompatible code-generation settings, while the AOT image
builder and final build verify that every artifact uses the same RIT layout and
link-target numbering.

#subsection[Garbage-Collection Integration]

$space$ SpiderMonkey uses a `JitCode` type to wrap a pointer to executable code. This
pointer normally refers to heap-allocated JIT instructions owned by the
`JitCode` object. AmberMonkey instead points it into the immutable `.text.aot`
region of the engine library. Transparently reusing the `JitCode` interface
allows AOT artifacts to integrate with existing consumers, including profiling,
stack walking, and transfers between Baseline code and IC stubs.

The runtime can still discard objects that refer to image-backed instructions.
An IC site may discard its attached stubs when it becomes megamorphic, while a
self-hosted function's Baseline body may be discarded after the function tiers
up to optimized code. If a `JitCode` object becomes unreachable, the garbage collector must
reclaim the object without freeing static instructions that the JIT code
allocator never allocated. AmberMonkey marks the object as static to
communicate this distinction. Tracing skips the relocation tables used to find
embedded garbage-collected pointers, and finalization leaves `.text.aot` mapped
as part of the engine library. Capture excludes movable garbage-collected
pointers, so the omitted tracing has no movable pointers to update.

#subsection[Debugging and Profiling]

$space$ SpiderMonkey uses patchable code to debug guest JavaScript at run time,
independently of native debugging support for the engine binary. The Baseline
Interpreter contains debugger paths even in release builds, each initially
skipped by a `toggledJump`. On x86-64, enabling instrumentation changes the jump
into a same-sized comparison that falls through to the instrumented path.
Breakpoint and stepping sites instead replace patchable NOPs with calls to the
debug-trap handler.

AmberMonkey retains these patch sites in the image-backed Baseline Interpreter,
but does not install an image-backed Baseline body for a script already
marked as a debuggee. SpiderMonkey instead generates private code with the
required instrumentation. Profiling follows a similar split. Registering an
image-backed range in the profiler's native-to-bytecode map leaves its
instructions unchanged, while entry and exit instrumentation patches its
`toggledJump` sites.

Patching an image-backed range reduces cross-process sharing. AmberMonkey
temporarily changes the containing `.text.aot` pages from read-execute to
read-write, then restores read-execute permissions. The first write gives the
process a private copy of each affected page. Debugging or profiling therefore
forfeits sharing for those pages, while unmodified processes continue to share
the original image.

#subsection[Replacing RIT Accesses with Native-Linker Relocations]

$space$ Most embedded references are resolved through the RIT at run time.
References to non-interposable engine symbols visible at engine link time
instead use native-linker relocations. This replaces the RIT access with a
direct PC-relative reference. Run-time-generated, embedder-supplied, and
interposable dependencies remain in the RIT.

During capture, AmberMonkey zeros the four-byte PC-relative displacement for
each such reference and records its image offset and dependency identifier. The
AOT image builder uses these records to generate the assembly shim in
@lst-image-relocation. At each recorded field, an `.incbin` directive emits the
preceding artifact bytes into `.text.aot`, a `.long` directive emits a
relocation naming the corresponding engine symbol, and the next `.incbin`
resumes after the field. Repeating this sequence emits the complete artifact.
Copy-and-Patch similarly uses relocation records to identify binary fields for
run-time patching @xu2021copypatch, whereas AmberMonkey delegates their
resolution to the native linker.

#image-relocation-scaffold(placement: top)

At engine link time, the linker fills each recorded field with the PC-relative
displacement to the corresponding engine symbol. This displacement remains
valid under ASLR because relative positions within the engine library do not
change. The resulting reference requires neither dynamic relocation nor an RIT
lookup. The same construction applies when a compiler can record an embedded
reference and associate its dependency with a symbol resolved during final
linkage.

#subsection[Mirroring Frequently Read State]

$space$ Most RIT slots hold addresses, so reading the referenced state requires a
second dependent load. AmberMonkey avoids this load by mirroring frequently
polled scalars directly in the RIT, including the interrupt state, JIT stack
limit, and count of zones requiring pre-write barriers. Mutation paths update
these entries, using atomic stores when another thread may read them. A nonzero
barrier count falls back to the precise per-zone test. We evaluate native-linker
relocations and value mirroring separately.

#subsection[Prototype Scope and Limitations]

$space$ AmberMonkey adds 3.7K lines of code. Its dependency tables name 85
non-function targets: 20 core runtime pointers, 18 table-derived typed-array
addresses, and 47 other engine targets. Function dependencies reuse 119
existing ABI entries and add 85 AOT-specific entries. The RIT also reserves
512 automatically indexed VM-wrapper slots. Offline capture recognized every
dependency in 24,265 unique tp6-Train artifacts. AmberMonkey also passes all
tests in SpiderMonkey's imported Test262 suite.

An artifact enters the image only when AmberMonkey can express every embedded
reference as a native-linker relocation or RIT access. The x86-64 prototype
aborts capture for movable garbage-collected pointers and retargetable table
entries. It omits AOT generation of optimized Ion code, although the design
does not preclude it.

#section[Experimental Methodology]

#subsection[Research Setup]

$space$ This study evaluates AmberMonkey in matched release builds of
Firefox 153.0a1 on x86-64. Experiments run on an AMD Ryzen 5 7640U system
with 6 cores, 12 hardware threads, and 32 GB of memory under NixOS 26.05 and
Linux 7.0.9. During measurement, the setup disables frequency boost and
simultaneous multithreading (SMT), selects the `performance` governor, and
runs no other user workloads. Both builds disable profile-guided and
link-time optimization.

We collect 10 independent runs per benchmark and configuration for every
experiment. Each run uses a fresh process, and browser runs use a fresh profile.
The 10 runs form randomized blocks with one execution of each configuration per
block. The Raptor harness serves Speedometer 3.1 and JetStream 3.0 locally.
Browser runs disable Firefox's content sandbox so experimental settings reach
content processes. Speedometer executes five
page cycles per run; JetStream executes one. JetStream retains SpiderMonkey's
WebAssembly compiler, so its measurements include the benefit of WebAssembly
compilation.

Results report arithmetic means unless aggregating ratios across benchmarks or
workload components, for which we use geometric means. Pairwise comparisons
compute ratios within each randomized block. Error bars show one standard
deviation across the 10 runs.

#subsection[Corpus Construction]

$space$ The recording build applies the selection policy from the final
subsection of Section III. It records the union of #ic-stub-count CacheIR
bodies requested by tp6-Train and excludes application Baseline functions. The
corpus also includes the deterministic Baseline Interpreter and all
#self-hosted-fn-count eligible self-hosted Baseline functions. SpiderMonkey
implements parts of the ECMAScript standard library as self-hosted JavaScript,
so their bytecode is known during the trusted build. The packed image occupies
#corpus-packed-size and is fixed before collecting results. tp6-Test,
Speedometer 3.1, and JetStream 3.0 do not participate in corpus construction.

#subsection[Execution Configurations]

$space$ @tab-execution-configurations defines four principal evaluated
configurations. Interpreter-only and #am prohibit guest-code JIT compilation;
#am instead executes artifacts from the fixed AOT corpus. #baseline-jit permits
Baseline compilation but disables Ion, while #default-ion enables all tiers.

#figure(
  execution-configurations-table(),
  caption: [Execution configurations. Guest-code JIT denotes JavaScript
    Baseline, CacheIR stub-body, and optimizing compilation.],
  placement: top,
) <tab-execution-configurations>

#section[Evaluation]

#linebreak()

$space$ The evaluation yields three main findings. First, fine-grained IC bodies
generalize across applications: #ic-stub-count CacheIR bodies serve
#sp3-ic-hit-rate of Speedometer 3.1 and #js3-ic-hit-rate of JetStream 3.0 IC
requests, while complete Baseline functions show little cross-workload reuse.
Second, AmberMonkey improves restricted Speedometer 3.1 throughput by
#sp3-aot-speedup over interpretation, reaching #sp3-aot-over-bl-fraction of
Baseline-JIT throughput. Third, sharing image-backed code reduces tier-matched
executable-code PSS per content process by #jit-memory-reduction while increasing the
Firefox engine binary by #libxul-growth (#libxul-growth-pct).

#subsection[Corpus Coverage]
$space$ This evaluation measures tp6-Train corpus coverage on
three held-out workload sets. The tp6-Test set contains sites from the same
page-load suite but is disjoint from tp6-Train. Speedometer 3.1 models
interactive web applications, while JetStream 3.0 contains JavaScript and
WebAssembly workloads. None participates in corpus construction.

//*NELSON: I do not know what "Installed" means for either the Baseline Interpreter or the Baseline Compiled Function bodies in Table 3. We should have a sentence to help readers with understanding this table.

@tab-coverage reports held-out coverage for the three artifact classes.
Utilization is the fraction of corpus entries used by a workload; AOT hit rate
is the fraction of dynamic requests served by the image. For the Baseline
Interpreter, installations count SpiderMonkey runtimes that use the single
image-backed interpreter instead of generating a private copy.

#figure(
  coverage-table(),
  caption: [Held-out coverage of the fixed AOT corpus. Group headings report
    corpus size. The CacheIR corpus serves nearly all attachment requests in
    each workload.],
  placement: top,
) <tab-coverage>

The tp6-Train IC corpus serves #tp6-test-ic-hit-rate of requests on tp6-Test,
#sp3-ic-hit-rate on Speedometer 3.1, and #js3-ic-hit-rate on JetStream 3.0. The
tp6-Test result shows generalization to disjoint sites from the same
suite, while JetStream's lower rate indicates slightly less coverage for its
distinct workload mix. The corpus of Baseline bodies includes only
build-time-known self-hosted functions; its coverage does not predict
application functions.

#subsection[Restricted Execution]

//*NELSON: This paragraph is pretty much stating what the graph shows (reading the graph) withoug\t much analysis. What is the significance of these numbers?

$space$ @fig-amber-perf-speed3 reports Speedometer 3.1 speedup per workload for
each configuration relative to the interpreter-only baseline. The rightmost
group is the geometric mean of the #sp3-workload-count workload ratios and
equals the aggregate-score ratio. #am execution reaches
#sp3-aot-ratio, #baseline-jit reaches #sp3-bl-ratio,
and #default-ion reaches #sp3-default-ratio. Both restricted
configurations disable guest-code JIT compilation, so their difference isolates
the performance recovered by the immutable corpus: #am recovers
#sp3-aot-over-bl-fraction of #baseline-jit throughput and reaches
#sp3-aot-default-fraction of default-tier throughput, a
#sp3-aot-speedup improvement over interpretation.

#fig(
  "lib/figures/7-3-amber-perf-speed3-workloads.pdf",
  [Speedometer 3.1 per-workload speedup over #interp-only-prose. The geomean
   of the 20 ratios is at the right. The #interp-only-prose baseline is
   implicit at the dashed 1× line. #am-ic omits AOT Baseline
   functions to isolate the IC corpus's contribution. #baseline-jit runs
   run-time-generated Baseline code with Ion disabled. #default-ion is
   unrestricted SpiderMonkey.],
  placement: top,
  scope: "parent",
) <fig-amber-perf-speed3>


#subsection[Comparison with V8 Jitless]

$space$ V8 exposes a `--jitless` flag that disables all run-time code generation,
including its Sparkplug baseline compiler, Maglev, and TurboFan optimizing
tiers @gruber2019jitless. It serves as the closest production analogue to
AmberMonkey's restricted-execution configuration: both prohibit
guest-triggered JavaScript code emission and rely on pre-generated engine code
plus a generic interpreter to execute JavaScript.

@fig-jitless-comparison compares restricted execution on Speedometer 3.1.
V8 Jitless reaches 66.2% of V8's default throughput, and AmberMonkey reaches
67.2% of SpiderMonkey's default throughput.

#fig(
  "lib/figures/7-3-v8-jitless-comparison.pdf",
  [Speedometer 3.1 throughput normalized to each engine's default
   configuration. *NOTE: n=1 and AM has regex + wasm, while V8 has PGO*],
  placement: top,
) <fig-jitless-comparison>

#subsection[AOT Image Installation Cost]

$space$ Installing an AOT artifact reconstructs its per-runtime objects and
metadata and associates them with image-backed machine code. Generating the
equivalent artifact at run time takes 5.01--37.9× as long per call as
installation (@tab-aot-attachment-cost). The experiment compares Firefox
`cpstartup` on the same AOT-enabled binary with the image enabled and disabled;
both configurations retain fallback compilation. Because installation and
compilation occur a different number of times, the table reports both calls
per content process and time per call. The ratio compares per-call costs, not
total startup cost.

#figure(
  aot-installation-cost-table(),
  caption: [AOT installation and run-time compilation costs during Firefox
    `cpstartup`. Counts are means per content process; times
    are per-call means aggregated across content-process records. Compile /
    Install divides run-time compilation time by AOT installation time.],
  placement: top,
) <tab-aot-attachment-cost>

#subsection[Indirection Overhead]

$space$ Across the #indirection-benchmark-count microbenchmarks, the geometric mean
ratio of per-iteration cycles for AmberMonkey artifacts to their
run-time-generated counterparts is #indirection-ratio
(@fig-indirection-overhead). This ratio corresponds to #indirection-overhead
overhead. AmberMonkey artifacts retire #indirection-ipi-overhead more
instructions but achieve
#indirection-ipc-delta higher instructions per cycle (IPC). The higher IPC
suggests that some added indirection work occupies otherwise idle pipeline
capacity, partially absorbing its instruction cost.

The microbenchmarks are simple fixed-iteration steady-state loops that isolate
indirection from corpus misses. Five targeted loops
repeatedly execute paths where image-backed code resolves runtime-specific
state, including frequent RIT accesses: the interrupt check, stack check,
pre-barrier, VM call, and local ABI call. Three controls exercise integer
arithmetic, monomorphic property loads, and dense-array loads, whose hot paths
do not directly exercise these references. The experiment compares the #am and
#baseline-jit configurations from @tab-execution-configurations; both disable
Ion. An exact corpus containing all #indirection-benchmark-count
microbenchmarks eliminates AOT misses. Linux `perf stat` records user-mode
cycles and retired instructions.
@fig-amber-perf-speed3 separately measures end-to-end performance.

#fig(
  "lib/figures/7-7-indirection-overhead.pdf",
  [User-mode cycles per iteration for run-time-generated and AmberMonkey
   artifacts with Ion disabled. The dotted rule separates
   #indirection-targeted-count indirection-sensitive
   microbenchmarks from #indirection-control-count controls; GM is the
   geometric mean of the #indirection-benchmark-count per-benchmark ratios.],
  placement: top,
) <fig-indirection-overhead>


#subsection[Cross-Process Memory Sharing]

$space$ This evaluation measures PSS for shared file-backed engine code and
private run-time-generated code during Speedometer 3.1. We exclude total browser
PSS because rendering and layout state vary independently of JavaScript code
generation. @fig-sp3-memory reports peak executable-code PSS.

Under #am, the aggregate resident set size of shared file-backed engine code is
#sp3-aot-libxul-sharing its PSS across #sp3-content-procs content processes.
Adding the image increases aggregate resident set size by #sp3-image-rss-growth
but PSS by only #sp3-image-pss-growth, confirming that processes share its
physical pages. Against the tier-matched, Ion-disabled #baseline-jit, #am
reduces executable-code PSS per process from
#sp3-runtime-per-proc-pss to #sp3-aot-per-proc-pss, a #jit-memory-reduction
reduction. We exclude the default configuration because Ion changes its code
profile.

#fig(
  "lib/figures/7-5-per-proc-pss.pdf",
  [Speedometer 3.1 executable-code PSS per content process at peak, decomposed
   into shared file-backed and private run-time-generated code. Under #am the
   private component collapses while the shared component stays flat, so
   executable-code PSS drops from
   #sp3-runtime-per-proc-pss (#baseline-jit) to #sp3-aot-per-proc-pss.],
  placement: top,
) <fig-sp3-memory>


#subsection[Binary Size]

$space$ AmberMonkey increases the Firefox engine binary on disk by
#libxul-growth (#libxul-growth-pct), from #libxul-default-size to
#libxul-aot-size. We measure the file-backed `PT_LOAD` segments of
`libxul.so` with `readelf` in matched release builds; the Firefox
launcher does not contain SpiderMonkey. The embedded AOT image occupies
#aot-image-size, measured between `aot_image_start` and `aot_image_end`,
while the remaining #nonimage-growth comprises other linked code and
alignment overhead. The linker folds the `.text.aot` input section into
the executable `.text` output section.

#section[Related Work]

#linebreak()

$space$ Partial evaluation can derive compilation by specializing an interpreter to a
fixed program @futamura1971partial. SpiderMonkey's Portable Baseline
Interpreter (PBL) executes JavaScript bytecode with CacheIR; Weval specializes
PBL for bytecode already present in a WebAssembly snapshot and combines it with
AOT IC stubs @fallin2025weval. AmberMonkey instead builds its image before guest
programs are known. It includes the deterministic Baseline Interpreter,
build-time-known self-hosted Baseline bodies, and CacheIR stub bodies requested
across workloads rather than specializing guest bytecode.

_Reusable Inline Caching_ (RIC) carries context-independent IC information from
one execution into later executions and eagerly repopulates IC state to avoid
cold misses @choi2019ric. AmberMonkey currently attaches stubs only after a
run-time observation. Its AOT corpus materializes the native body in advance,
making eager attachment easier. The remaining problem is reconstructing
site-specific fields such as shapes and slot offsets.

ShareJIT provides Android Runtime processes with a global cache of
run-time-compiled methods and limits context-dependent optimization to improve sharing
@xu2018sharejit. AmberMonkey instead freezes selected Baseline code during
a trusted build. Firefox processes map them through the engine library without
coordinating cache ownership or adding guest-generated instructions, while
private metadata and indirection tables supply per-runtime state.

GraalVM Native Image compiles reachable Java code under a closed-world
assumption, while Dart AOT produces architecture-specific machine code for a
specified Dart program @graalvm2026nativeimage @dart2025compile. Both know the
application at build time. AmberMonkey instead targets a browser engine whose
guest programs arrive after the engine is built. It precompiles engine-generated
code selected independently of any one guest application.

V8's embedded builtins place isolate-independent generated code in the
engine binary and keep isolate-specific state separate, eliminating private
builtin copies @gruber2018builtins. V8 Jitless instead disables run-time
executable memory and executes JavaScript without its JIT tiers
@gruber2019jitless. AmberMonkey applies file-backed sharing to the Baseline
Interpreter, self-hosted Baseline bodies, and CacheIR stub bodies. Its fixed
corpus recovers native execution under a similar restriction.

#section[Conclusion]

#linebreak()

$space$ We presented AmberMonkey, a general approach to AOT compilation for a
Baseline tier. Our evaluation identifies three artifact kinds suited to AOT
compilation for separate reasons. IC bodies recur across workloads, allowing a
small corpus to achieve high dynamic coverage on unseen workloads. Complete
Baseline bodies recur less often, but self-hosted code, including JavaScript
builtins, provides a common corpus. The deterministic Baseline Interpreter can
also be shared to avoid redundant compilation across processes.

// #section[Future Work]
//
// #linebreak()
//
// $space$ Decoupling JIT compilation from the process that consumes its output
// creates opportunities for offline optimization.
//
// #linebreak()
//
// 1. _Eager IC stub attachment_: By using the initial engine invocation to
//    collect profiling information about which IC stubs attach at particular
//    script locations, a later run may skip expensive fallback-stub routines
//    through eager attachment. Choi et al. established the utility of avoiding
//    the fallback stub @choi2019ric. AmberMonkey already stores the native stub
//    bodies, but eager attachment also requires a serializable format for stub
//    parameters such as object shapes.
//
// #linebreak()
//
// 2. _Type-specialized builtins_: Previous work with V8's Torque DSL demonstrates
//    that type-specialized fast paths can improve JavaScript builtins. Common
//    operand-type patterns can establish early control-flow paths independent of
//    generic handlers, allowing more aggressive specialization in Baseline code.
//

#bibliography("bib.yaml", style: "ieee")


// #section("Draft Notes")
//
// #TODO("Rename Concurrent VMs")
// #TODO("Rerun JITless comparisson with n=10")
// #TODO("Turn off regex compiler for all AM evals")
// #TODO("Replace the AOT Image figure with a nicer one")
//
// #NOTE("1) The 7% indirection overhead: This is done on some micro-benchmarks which specfically exercise the areas affected by AmberMonkey. Should we do a stock: `--no-ion` v.s AOT: `--aot-only` over Speedometer3 to isolate E2E Baseline tier indirection overhead? We will likely get a much lower number than 7%. Maybe 2-3%. Chase and I both found around 5% prior to slight 'optimziations'.")
//
// #NOTE("4) We are missing performance metrics for how long AOT loading takes: deserialization, time filling the RIT (Runtime Indirection Table), etc.")
//
// #NOTE("8) The execution configurations introduced in the methodology don't necessarily line up with those used in the evaluation. There is generally too much inconsitency around what execution modes are used and their abbreviations.")


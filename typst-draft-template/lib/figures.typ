#import "../diagrams/figure_1_ic.typ": ic-shared-diagram
#import "../diagrams/figure_2_rit.typ": ambermonkey-runtime-diagram
#import "../diagrams/figure_3_aot_image.typ": aot-image-diagram
#import "figure-placement.typ": figure-body, figure-placement, figure-scope

#let fig-desc(body, title: "Figure description") = block(
  fill: luma(245),
  stroke: (left: 3pt + luma(180)),
  inset: (x: 12pt, y: 10pt),
  radius: 2pt,
  width: 100%,
  [
    #text(size: 9pt, weight: "bold", fill: luma(80), tracking: 0.5pt)[
      #upper(title)
    ]
    #v(4pt, weak: true)
    #body
  ],
)

#let eval-desc(body, title: "Evaluation") = block(
  fill: luma(245),
  stroke: (left: 3pt + luma(140)),
  inset: (x: 12pt, y: 10pt),
  radius: 2pt,
  width: 100%,
  [
    #text(size: 9pt, weight: "bold", fill: luma(80), tracking: 0.5pt)[
      #upper(title)
    ]
    #v(4pt, weak: true)
    #body
  ],
)

#let _overview-box(title, body, stroke: luma(145), fill: white) = block(
  width: 100%,
  inset: 6pt,
  stroke: 0.6pt + stroke,
  fill: fill,
  radius: 2pt,
  [
    #align(center)[#text(size: 7.5pt, weight: "bold")[#title]]
    #v(3pt)
    #text(size: 7pt)[#body]
  ],
)

#let rit-access(placement: top) = [
  #figure(
    align(center)[
      #scale(x: 90%, y: 90%, reflow: true)[#ambermonkey-runtime-diagram]
    ],
    kind: image,
    supplement: [Figure],
    caption: [Runtime Indirection Table (RIT) access. Each run-time-generated
      Baseline Interpreter embeds its runtime address directly. The shared
      ahead-of-time (AOT) Baseline Interpreter instead loads the current RIT
      from its Baseline frame and resolves `JSRuntime` through a slot.
      Indirection lets concurrent virtual machines (VMs) share one AOT Baseline
      Interpreter while retaining private RITs and program stacks.],
    placement: placement,
    scope: "parent",
  ) <fig-rit-access>
]

#let cacheir-sharing-example(placement: top, at: none) = [
  #figure(
    figure-body(at, ic-shared-diagram),
    kind: image,
    supplement: [Figure],
    caption: [Two property-load sites share a fixed-slot CacheIR body. Each
      site enters indirectly through its current stub's code pointer, while
      site-local stub data parameterizes the body. On a guard failure, the
      failure path follows the `next` pointer and enters the newly selected
      stub's body.],
    placement: figure-placement(at, placement),
    scope: figure-scope(at, "column"),
  ) <fig-cacheir-sharing>
]

#let string-int32-cacheir(placement: auto, scope: "column", at: none) = [
  #figure(
    figure-body(at, {
      set text(size: 7.2pt)
      grid(
        columns: (0.9fr, auto, 1.35fr),
        gutter: 4pt,
        block(
          width: 100%,
          stroke: 0.6pt + gray,
          inset: (x: 5pt, y: 6pt),
          radius: 2pt,
        )[
          *Observed operation*
          #v(4pt)
          #raw(
            "const lhs = \"41\";\nconst rhs = 1;\nlhs - rhs;",
            lang: "js",
            block: true,
          )
        ],
        align(center + horizon)[#text(size: 12pt)[→]],
        block(
          width: 100%,
          stroke: 0.6pt + gray,
          inset: 4pt,
          radius: 2pt,
        )[
          *Generated CacheIR*
          #v(2pt)
          #raw("GuardToString(lhs) -> str\nGuardStringToInt32(str) -> lhs32\nGuardToInt32(rhs) -> rhs32\nInt32SubResult(lhs32, rhs32)", block: true)
        ],
      )
      v(3pt)
      align(center)[_Baseline CacheIR compiler_ $arrow.r$ _one native stub body_]
    }),
    caption: [CacheIR compiles string–integer subtraction into one specialized
      native stub body.],
    kind: image,
    placement: figure-placement(at, placement),
    scope: figure-scope(at, scope),
  ) <fig-string-int32-cacheir>
]

#let aot-image-layout(placement: top) = [
  #figure(
    aot-image-diagram,
    kind: image,
    supplement: [Figure],
    caption: [Packed AmberMonkey image. Directory entries locate
      schema-defined metadata records and, for executable artifacts, aligned
      instruction bodies. A page boundary separates the code region from image
      metadata.],
    placement: placement,
    scope: "column",
  ) <fig-aot-image-layout>
]

#let image-relocation-scaffold(placement: top) = {
  show raw.where(block: true): set text(
    font: "DejaVu Sans Mono",
    size: 7pt,
  )

  let source = ```asm
  .section .text.aot

  # Emit bytes preceding the displacement field.
  .incbin "AOTImage.inc", 0, disp_offset

  # Emit a relocation in place of the zero field.
  .long engine_symbol - . - 4

  # Resume after the four-byte field.
  .incbin "AOTImage.inc", disp_offset + 4
  ```

  [
    #figure(
      block(
        width: 100%,
        inset: (x: 8pt, y: 5pt),
        raw(source.text, lang: "asm", block: true),
      ),
      kind: raw,
      supplement: [Listing],
      caption: [Conceptual assembly for one relocated displacement field. The
        first `.incbin` emits the preceding bytes, `.long` emits a symbolic
        relocation in place of the zero field, and the second `.incbin` resumes
        after the field. The native linker resolves the relocation.],
      placement: placement,
    ) <lst-image-relocation>
  ]
}

#let _fig(path, caption, placement: top, width: auto, height: auto, scope: "column") = {
  let w = if width == auto and height == auto { 100% } else { width }
  figure(
    image(path, width: w, height: height),
    caption: caption,
    placement: placement,
    scope: scope,
  )
}

#let _listing-panel(title, source, lang, emphasis: none) = {
  show raw.line: line => {
    if emphasis != none and line.text.contains(emphasis) {
      let parts = line.text.split(emphasis)
      text(font: "DejaVu Sans Mono", size: 7pt, parts.first())
      text(
        font: "DejaVu Sans Mono",
        size: 7pt,
        weight: "bold",
        emphasis,
      )
      text(
        font: "DejaVu Sans Mono",
        size: 7pt,
        parts.slice(1).join(emphasis),
      )
    } else {
      line
    }
  }

  block(
    width: 100%,
    height: 1.15in,
    inset: (x: 5pt, y: 4pt),
    [
      #align(center)[
        #text(size: 7.5pt, weight: "bold")[#title]
      ]
      #v(5pt)
      #raw(source, lang: lang, block: true, theme: none, tab-size: 2)
    ],
  )
}

#let code-lowering-panel(placement: top) = {
  show raw.where(block: true): set text(
    font: "DejaVu Sans Mono",
    size: 7pt,
  )

  let generator = ```cpp
  void emitCheck(Masm& masm, Reg out) {
    auto* flag = cx->interruptFlag();
    masm.movePtr(ImmPtr(flag), out);
    masm.branch32(NonZero,
      Address(out, 0), &interrupt);
  }
  ```

  let capture = ```cpp
  void movePtr(ImmPtr p, Reg dst) {
    if (auto s = findRITSlot(p)) {
      emitRITLoad(*s, dst);
      return;
    }
    reportUnknownPointer(p);
  }
  ```

  let emitted = ```asm
  # Before
  movabsq $flag, %rax

  # After
  movq -24(%rbp), %r11  # table
  movq  48(%r11), %rax # slot
  ```

  [
    #figure(
      grid(
        columns: (1fr, 1fr, 1fr),
        gutter: 10pt,
        align: top,
        _listing-panel(
          [(a) Baseline code generator],
          generator.text,
          "cpp",
          emphasis: "ImmPtr(flag)",
        ),
        _listing-panel(
          [(b) Simplified lowering],
          capture.text,
          "cpp",
          emphasis: "emitRITLoad",
        ),
        _listing-panel([(c) Schematic x86-64], emitted.text, "asm"),
      ),
      kind: raw,
      supplement: [Listing],
      caption: [Simplified illustration of transparent runtime-pointer
        lowering. Panel (a) represents Baseline Interpreter code generation
        with no AOT-specific logic. The MacroAssembler reverse-maps its direct
        pointer in panel (b) and emits the RIT access shown in panel (c).
        Identifiers and offsets are schematic.],
      placement: placement,
      scope: "parent",
    ) <lst-code-lowering>
  ]
}

#let runtime-coupling-example(placement: top) = {
  show raw.where(block: true): set text(
    font: "DejaVu Sans Mono",
    size: 7pt,
  )

  let emphasis = "ImmPtr(&runtime->wellKnownSymbols())"
  show raw.line: line => {
    if line.text.contains(emphasis) {
      let parts = line.text.split(emphasis)
      text(font: "DejaVu Sans Mono", size: 7pt, parts.first())
      text(
        font: "DejaVu Sans Mono",
        size: 7pt,
        weight: "bold",
        emphasis,
      )
      text(
        font: "DejaVu Sans Mono",
        size: 7pt,
        parts.slice(1).join(emphasis),
      )
    } else {
      line
    }
  }

  let source = ```cpp
  LoadUint8Operand(masm, scratch1);
  masm.movePtr(
      ImmPtr(&runtime->wellKnownSymbols()), scratch2);
  masm.loadPtr(
      BaseIndex(scratch2, scratch1, ScalePointer), scratch1);
  // ...
  ```

  [
    #figure(
      block(
        width: 100%,
        inset: (top: 5pt, bottom: 5pt),
        raw(source.text, lang: "cpp", block: true, theme: none),
      ),
      kind: raw,
      supplement: [Listing],
      caption: [Excerpt from `emit_Symbol` in SpiderMonkey's generated Baseline
        Interpreter. `ImmPtr` embeds the address of the generating runtime's
        well-known-symbol table in the emitted instructions.],
      placement: placement,
    ) <lst-symbol-coupling>
  ]
}

#let sharability(width: auto, height: auto, placement: top) = [
  #_fig(
    "./figures/3-2-sharability.png",
    [Peak JIT residency at TabsOpen across the browser's content
     processes. Blue segments are sharable, red is unique memory.
     App = application Baseline code, Tr = trampolines, Ion = Ion code, IC =
     attached Baseline IC bodies, BI = Baseline Interpreter, SH = self-hosted
     Baseline code, Tot = row-wise sum.],
    width: width,
    height: height,
    placement: placement,
  ) <fig-sharability>
]

#let banded-cdf(width: auto, height: auto, placement: top, scope: "column") = [
  #_fig(
    "./figures/3-3-banded-IC-CDF.png",
    [Ranked cumulative distribution of dynamic inline-cache (IC) stub-body
     attachments across eight web workloads. The solid curve reports the
     median, the band spans the per-rank minimum and maximum, and the dashed
     curves show the least and most concentrated workloads. A small subset of
     compiled bodies serves most dynamic attachments.],
    width: width,
    height: height,
    placement: placement,
    scope: scope,
  ) <fig-ic-cdf>
]

#let ic-jaccard(width: auto, height: auto, placement: top, scope: "column") = [
  #_fig(
    "./figures/3-4-ic-jaccard.png",
    [The lower triangle reports the Jaccard index of executed inline-cache
     bodies across eight sites. The upper triangle reports one direction of
     frequency-weighted coverage for each unordered site pair; the omitted
     reverse direction can differ.],
    width: width,
    height: height,
    placement: placement,
    scope: scope,
  ) <fig-ic-jaccard>
]

#let ic-micro-speedup(width: auto, height: auto, placement: top, scope: "column") = [
  #show figure: set figure(gap: 2pt)
  #_fig(
    "./figures/3-4-sm-v8-ics-micro-bench.pdf",
    [Loop-adjusted V8/SM cost by operation. Positive values favor SpiderMonkey
     CacheIR. Negative values favor V8 Sparkplug. The y-axis reports
     $log_2("V8" \/ "SM")$.],
    width: width,
    height: height,
    placement: placement,
    scope: scope,
  ) <fig-ic-micro-speedup>
]

#let jitless-s3-perf(width: auto, height: auto, placement: top, scope: "column") = [
  #_fig(
    "./figures/7-1-jitless-s3-perf.png",
    [Speedometer 3.1 performance normalized to bytecode-only execution.
     AmberMonkey configurations progressively restore performance as AOT
     IC and Baseline artifacts are enabled.],
    width: width,
    height: height,
    placement: placement,
    scope: scope,
  ) <fig-jitless-s3-perf>
]


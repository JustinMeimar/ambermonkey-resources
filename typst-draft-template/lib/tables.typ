#let fmt-cell(val, fmt) = {
  if fmt == "int" { str(int(val)) }
  else if fmt == "percent" { str(calc.round(val * 100, digits: 2)) + "%" }
  else if fmt == "float" { str(calc.round(val, digits: 3)) }
  else { str(val) }
}

// Semantic constructors for compact, grouped research tables. Keeping row
// structure separate from Typst's table primitives makes the declarations
// straightforward to reproduce with LaTeX tabular, booktabs, and multicolumn.
#let table-row(..cells) = (kind: "row", cells: cells.pos())
#let table-section(title) = (kind: "section", title: title)

#let _section-cell(title, column-count, fill) = table.cell(
  colspan: column-count,
  fill: fill,
)[#title]

#let sectioned-table(
  columns: none,
  header: none,
  rows: none,
  align: left,
  text-size: 8pt,
  inset: (x: 3pt, y: 2pt),
  stroke: 0.4pt + gray,
  section-fill: luma(235),
) = {
  assert(columns != none, message: "sectioned-table requires columns")
  assert(header != none, message: "sectioned-table requires a header")
  assert(rows != none, message: "sectioned-table requires rows")
  let column-count = header.len()
  let cells = ()

  for row in rows {
    if row.kind == "section" {
      cells.push(_section-cell(strong(row.title), column-count, section-fill))
    } else {
      assert(
        row.kind == "row",
        message: "unknown sectioned-table row kind: " + str(row.kind),
      )
      assert(
        row.cells.len() == column-count,
        message: "sectioned-table row has the wrong number of cells",
      )
      for cell in row.cells {
        cells.push(cell)
      }
    }
  }

  block(text(size: text-size)[
    #table(
      columns: columns,
      align: align,
      inset: inset,
      stroke: stroke,
      table.header(..header.map(cell => strong(cell))),
      ..cells,
    )
  ])
}

#let render-table(data) = {
  let cols = data.columns
  let font-size = data.at("text_size", default: 9) * 1pt
  let cell-inset = data.at("cell_inset", default: 5) * 1pt
  let column-layout = if "column_weights" in data {
    data.column_weights.map(weight => weight * 1fr)
  } else {
    cols.len()
  }
  let aligns = cols.map(c => {
    let a = c.at("align", default: "left")
    if a == "right" { right } else if a == "center" { center } else { left }
  })
  let cells = ()
  for row in data.rows {
    for (i, v) in row.enumerate() {
      cells.push(fmt-cell(v, cols.at(i).at("format", default: "str")))
    }
  }
  block(text(size: font-size)[
    #if "title" in data [ *#data.title* #v(0.4em) ]
    #table(
      columns: column-layout,
      align: (col, _) => aligns.at(col),
      inset: cell-inset,
      stroke: 0.5pt + gray,
      table.header(..cols.map(c => strong(c.label))),
      ..cells,
    )
  ])
}

#let table-from-json(name) = render-table(json("json/" + name))

#let render-transposed-table(data) = {
  let cols = data.columns
  let font-size = data.at("text_size", default: 9) * 1pt
  let cell-inset = data.at("cell_inset", default: 5) * 1pt
  let column-layout = (1.6fr,)
  for _ in data.rows {
    column-layout.push(1fr)
  }
  let header = (strong(cols.at(0).label),)
  for row in data.rows {
    header.push(strong(fmt-cell(
      row.at(0),
      cols.at(0).at("format", default: "str"),
    )))
  }
  let cells = ()
  for i in range(1, cols.len()) {
    let col = cols.at(i)
    cells.push(strong(col.label))
    for row in data.rows {
      cells.push(fmt-cell(row.at(i), col.at("format", default: "str")))
    }
  }
  block(width: 100%, text(size: font-size)[
    #table(
      columns: column-layout,
      align: (col, _) => if col == 0 { left } else { right },
      inset: cell-inset,
      stroke: 0.5pt + gray,
      table.header(..header),
      ..cells,
    )
  ])
}

#let transposed-table-from-json(name) = {
  render-transposed-table(json("json/" + name))
}

#let json-field(name, key) = {
  let data = json("json/" + name)
  assert(key in data, message: name + ": no field " + key)
  data.at(key)
}

#let cell-from-table(name, row-label, col-key) = {
  let data = json("json/" + name)
  let col-idx = data.columns.position(c => c.key == col-key)
  assert(col-idx != none, message: name + ": no column with key " + col-key)
  let row = data.rows.find(r => r.at(0) == row-label)
  assert(row != none, message: name + ": no row labelled " + str(row-label))
  let col = data.columns.at(col-idx)
  fmt-cell(row.at(col-idx), col.at("format", default: "str"))
}

#let cell-value(name, row-label, col-key) = {
  let data = json("json/" + name)
  let col-idx = data.columns.position(c => c.key == col-key)
  assert(col-idx != none, message: name + ": no column with key " + col-key)
  let row = data.rows.find(r => r.at(0) == row-label)
  assert(row != none, message: name + ": no row labelled " + str(row-label))
  row.at(col-idx)
}


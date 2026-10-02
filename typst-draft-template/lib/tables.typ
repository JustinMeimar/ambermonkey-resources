#let _row-value(row, column, index) = {
  row.at(if type(row) == dictionary { column.key } else { index })
}

#let json-field(data, key) = data.at(key)

#let cell-value(table, key) = table.at(key)

#let cell-from-table = cell-value

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

#let render-table(data, ..options) = {
  let cols = data.columns
  let cells = ()
  for row in data.rows {
    for (index, column) in cols.enumerate() {
      cells.push(_row-value(row, column, index))
    }
  }
  table(
    ..((columns: cols.len()) + options.named()),
    table.header(..cols.map(column => strong(column.label))),
    ..cells,
  )
}

#let render-transposed-table(data, ..options) = {
  let cols = data.columns
  let first = cols.first()
  let header = (strong(first.label),) + data.rows.map(row => {
    strong(_row-value(row, first, 0))
  })
  let cells = ()
  for index in range(1, cols.len()) {
    let column = cols.at(index)
    cells.push(strong(column.label))
    for row in data.rows {
      cells.push(_row-value(row, column, index))
    }
  }
  table(
    ..((columns: data.rows.len() + 1) + options.named()),
    table.header(..header),
    ..cells,
  )
}

#let table-from-json(name, ..options) = render-table(json("json/" + name), ..options)
#let transposed-table-from-json(name, ..options) = render-transposed-table(json("json/" + name), ..options)

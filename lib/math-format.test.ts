import { describe, expect, test } from "bun:test"

import { normalizeMathText } from "./math-format"

describe("math text normalization", () => {
  test("turns copied loss matrices into LaTeX display math", () => {
    expect(normalizeMathText("λ = [[0, 100], [1, 0]]")).toBe(
      "$$\\lambda = \\begin{pmatrix}0 & 100 \\\\ 1 & 0\\end{pmatrix}$$"
    )
  })

  test("keeps authored LaTeX unchanged", () => {
    expect(normalizeMathText("Choose $p(x | C_1)$")).toBe("Choose $p(x | C_1)$")
  })
})

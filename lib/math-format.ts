export function normalizeMathText(text: string) {
  if (text.includes("$")) {
    return text
  }

  return text
    .replace(
      /λ\s*=\s*\[\[(\d+),\s*(\d+)\],\s*\[(\d+),\s*(\d+)\]\]/g,
      (_, a, b, c, d) =>
        `$$\\lambda = \\begin{pmatrix}${a} & ${b} \\\\ ${c} & ${d}\\end{pmatrix}$$`
    )
    .replace(/Ω=\(true,false\)/g, "$\\Omega=(\\mathrm{true},\\mathrm{false})$")
    .replace(/λ_ij/g, "$\\lambda_{ij}$")
    .replace(/TPR\s*>\s*FPR/g, "$\\mathrm{TPR} > \\mathrm{FPR}$")
    .replace(/TPR=0/g, "$\\mathrm{TPR}=0$")
    .replace(/0\.1\*0\.1/g, "$0.1\\cdot 0.1$")
    .replace(/0\.9\*0\.9/g, "$0.9\\cdot 0.9$")
}

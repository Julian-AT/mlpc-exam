"use client"

import * as React from "react"
import katex from "katex"

import { normalizeMathText } from "@/lib/math-format"
import { cn } from "@/lib/utils"

type MathTextProps = {
  as?: "div" | "span"
  className?: string
  text: string
}

type Segment =
  | {
      kind: "text"
      value: string
    }
  | {
      display: boolean
      kind: "math"
      value: string
    }

export function MathText({ as = "div", className, text }: MathTextProps) {
  const Component = as
  const segments = React.useMemo(
    () => parseMathSegments(normalizeMathText(text)),
    [text]
  )

  return (
    <Component className={cn("math-text", className)}>
      {segments.map((segment, index) => {
        if (segment.kind === "text") {
          return renderTextSegment(segment.value, index)
        }

        return (
          <span
            className={cn(
              segment.display
                ? "my-3 block overflow-x-auto py-1"
                : "inline-block align-baseline"
            )}
            dangerouslySetInnerHTML={{
              __html: katex.renderToString(segment.value, {
                displayMode: segment.display,
                strict: false,
                throwOnError: false,
                trust: false,
              }),
            }}
            key={index}
          />
        )
      })}
    </Component>
  )
}

function parseMathSegments(text: string): Segment[] {
  const segments: Segment[] = []
  const pattern = /(\$\$[\s\S]+?\$\$|\$[^$\n]+?\$)/g
  let cursor = 0

  for (const match of text.matchAll(pattern)) {
    const matchIndex = match.index ?? 0
    const token = match[0]

    if (matchIndex > cursor) {
      segments.push({ kind: "text", value: text.slice(cursor, matchIndex) })
    }

    const display = token.startsWith("$$")
    segments.push({
      display,
      kind: "math",
      value: display ? token.slice(2, -2) : token.slice(1, -1),
    })
    cursor = matchIndex + token.length
  }

  if (cursor < text.length) {
    segments.push({ kind: "text", value: text.slice(cursor) })
  }

  return segments
}

function renderTextSegment(value: string, key: number) {
  const lines = value.split("\n")

  return (
    <React.Fragment key={key}>
      {lines.map((line, index) => (
        <React.Fragment key={index}>
          {line}
          {index < lines.length - 1 && <br />}
        </React.Fragment>
      ))}
    </React.Fragment>
  )
}

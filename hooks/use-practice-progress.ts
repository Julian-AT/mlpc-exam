"use client"

import * as React from "react"

import {
  PRACTICE_STORAGE_KEY,
  createDefaultProgress,
  normalizeProgress,
} from "@/lib/practice"

import type { PracticeProgress } from "@/lib/practice"

export function usePracticeProgress() {
  const [isReady, setIsReady] = React.useState(false)
  const [progress, setProgress] = React.useState<PracticeProgress>(() =>
    createDefaultProgress()
  )

  React.useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setProgress(readStoredProgress())
      setIsReady(true)
    }, 0)

    return () => window.clearTimeout(timeoutId)
  }, [])

  React.useEffect(() => {
    if (!isReady) {
      return
    }
    window.localStorage.setItem(PRACTICE_STORAGE_KEY, JSON.stringify(progress))
  }, [isReady, progress])

  const resetProgress = React.useCallback(() => {
    setProgress(createDefaultProgress())
    window.localStorage.removeItem(PRACTICE_STORAGE_KEY)
  }, [])

  return {
    isReady,
    progress,
    resetProgress,
    setProgress,
  }
}

function readStoredProgress() {
  if (typeof window === "undefined") {
    return createDefaultProgress()
  }

  try {
    const storedValue = window.localStorage.getItem(PRACTICE_STORAGE_KEY)
    return storedValue
      ? normalizeProgress(JSON.parse(storedValue))
      : createDefaultProgress()
  } catch {
    return createDefaultProgress()
  }
}

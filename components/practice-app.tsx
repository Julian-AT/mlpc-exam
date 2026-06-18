"use client"

import * as React from "react"
import Image from "next/image"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  Bookmark02Icon,
  CheckmarkCircle02Icon,
  EraserIcon,
  Image02Icon,
} from "@hugeicons/core-free-icons"

import { MathText } from "@/components/math-text"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Progress } from "@/components/ui/progress"
import { Switch } from "@/components/ui/switch"
import { usePracticeProgress } from "@/hooks/use-practice-progress"
import { questionBank } from "@/lib/data"
import {
  createDrillSession,
  evaluateChoiceAnswer,
  getBestCurrentQuestionId,
  getDrillRemainingQuestionIds,
  getDisplayChoices,
  getMockExamStats,
  getMockRemainingSeconds,
  getMockReviewItems,
  getNextDrillQuestionId,
  getNextQuestionId,
  getOriginLabel,
  getPracticeQuestions,
  getPracticeStats,
  getPrimarySource,
  getQuestionNumber,
  getQuestionTopics,
  updateDrillSession,
  createMockExamSession,
} from "@/lib/practice"
import { cn } from "@/lib/utils"

import type { Choice, Question, Source, Topic } from "@/lib/data"
import type {
  MockReviewItem,
  PracticeMode,
  PracticeProgress,
  PracticeStats,
  PracticeSourceFilter,
} from "@/lib/practice"
import type { IconSvgElement } from "@hugeicons/react"

const EMPTY_SELECTION: string[] = []
const MOCK_EXAM_MINUTES = 45

type HeaderStats = Pick<PracticeStats, "answered" | "total">
type ProgressSetter = React.Dispatch<React.SetStateAction<PracticeProgress>>
type PracticeScreen = "menu" | "quiz" | "results"

export function PracticeApp() {
  const { progress, resetProgress, setProgress } = usePracticeProgress()
  const [screen, setScreen] = React.useState<PracticeScreen>("menu")
  const [now, setNow] = React.useState(() => Date.now())
  const [draftSelection, setDraftSelection] = React.useState<{
    choiceIds: string[]
    questionId: string
  } | null>(null)

  const filters = React.useMemo(
    () => ({
      mode: progress.mode,
      sourceFilter: progress.sourceFilter,
      topicId: progress.topicId,
    }),
    [progress.mode, progress.sourceFilter, progress.topicId]
  )
  const questions = React.useMemo(
    () => getPracticeQuestions(filters, progress),
    [filters, progress]
  )
  const stats = React.useMemo(
    () => getPracticeStats(questions, progress),
    [questions, progress]
  )
  const mockStats = React.useMemo(
    () => getMockExamStats(questions, progress.mockExam),
    [progress.mockExam, questions]
  )
  const drillRemainingIds = React.useMemo(
    () => getDrillRemainingQuestionIds(progress.drill),
    [progress.drill]
  )
  const remainingMockSeconds = getMockRemainingSeconds(progress.mockExam, now)
  const currentQuestionId = getBestCurrentQuestionId(
    questions,
    progress.currentByMode[progress.mode]
  )
  const question =
    questions.find((item) => item.id === currentQuestionId) ?? null
  const displayChoices = React.useMemo(
    () =>
      question ? getDisplayChoices(question, progress.shuffleChoices) : [],
    [progress.shuffleChoices, question]
  )
  const questionIndex = question
    ? questions.findIndex((item) => item.id === question.id)
    : -1
  const savedAnswer = question ? progress.answers[question.id] : undefined
  const isMockMode = progress.mode === "mock"
  const isDrillMode = progress.mode === "drill"
  const savedMockSelection =
    question && progress.mockExam ? progress.mockExam.answers[question.id] : []
  const selectedChoiceIds =
    question && draftSelection?.questionId === question.id
      ? draftSelection.choiceIds
      : isMockMode
        ? (savedMockSelection ?? EMPTY_SELECTION)
        : (savedAnswer?.selectedChoiceIds ?? EMPTY_SELECTION)
  const showFeedback =
    !isMockMode &&
    Boolean(savedAnswer) &&
    sameChoiceSet(selectedChoiceIds, savedAnswer?.selectedChoiceIds ?? [])
  const source = question ? getPrimarySource(question) : undefined
  const topics = question ? getQuestionTopics(question) : []
  const topicTitle = getSessionTitle(progress, topics)
  const isLastQuestion =
    questionIndex >= 0 && questionIndex === questions.length - 1
  const isDrillComplete =
    isDrillMode &&
    (progress.drill?.status === "completed" || drillRemainingIds.length === 0)
  const headerStats: HeaderStats = isMockMode
    ? { answered: mockStats.answered, total: mockStats.total }
    : stats
  const headerTitle =
    isMockMode && progress.mockExam?.status === "active"
      ? formatDuration(remainingMockSeconds)
      : topicTitle
  const coverage = isMockMode
    ? getPercent(mockStats.answered, mockStats.total)
    : stats.coverage

  const commitProgress = React.useCallback(
    (updater: (current: PracticeProgress) => PracticeProgress) => {
      setProgress((current) => ({
        ...updater(current),
        lastUpdatedAt: new Date().toISOString(),
      }))
    },
    [setProgress]
  )

  const startQuestionSet = React.useCallback(
    (
      mode: PracticeMode,
      topicId: "all" | string = "all",
      sourceFilter: PracticeSourceFilter = "all"
    ) => {
      setDraftSelection(null)
      commitProgress((current) => {
        const nextProgress = {
          ...current,
          mode,
          topicId,
          sourceFilter: mode === "exam" ? "all" : sourceFilter,
        }
        const nextQuestions = getPracticeQuestions(
          {
            mode,
            sourceFilter: nextProgress.sourceFilter,
            topicId,
          },
          nextProgress
        )

        return {
          ...nextProgress,
          currentByMode: {
            ...nextProgress.currentByMode,
            [mode]: getStartQuestionId(nextQuestions, nextProgress, mode),
          },
        }
      })
      setScreen("quiz")
    },
    [commitProgress]
  )

  const startMockExam = React.useCallback(
    (restart = false) => {
      setDraftSelection(null)
      setNow(Date.now())
      commitProgress((current) => {
        const examQuestions = getPracticeQuestions(
          { mode: "exam", sourceFilter: "all", topicId: "all" },
          current
        )
        const shouldResume =
          !restart &&
          current.mockExam?.status === "active" &&
          current.mockExam.questionIds.length > 0
        const mockExam =
          shouldResume && current.mockExam
            ? current.mockExam
            : createMockExamSession(
                examQuestions.map((item) => item.id),
                new Date().toISOString(),
                MOCK_EXAM_MINUTES
              )

        return {
          ...current,
          mode: "mock",
          topicId: "all",
          sourceFilter: "all",
          mockExam,
          currentByMode: {
            ...current.currentByMode,
            mock: shouldResume
              ? (getBestCurrentQuestionId(
                  examQuestions,
                  current.currentByMode.mock
                ) ??
                mockExam.questionIds[0] ??
                null)
              : (mockExam.questionIds[0] ?? null),
          },
        }
      })
      setScreen("quiz")
    },
    [commitProgress]
  )

  const startDrill = React.useCallback(
    (questionIds?: string[]) => {
      setDraftSelection(null)
      const hasQuestions =
        questionIds !== undefined
          ? questionIds.length > 0
          : getPracticeQuestions(
              { mode: "review", sourceFilter: "all", topicId: "all" },
              progress
            ).length > 0

      commitProgress((current) => {
        const reviewQuestions = getPracticeQuestions(
          { mode: "review", sourceFilter: "all", topicId: "all" },
          current
        )
        const drill = createDrillSession(
          questionIds ?? reviewQuestions.map((item) => item.id),
          new Date().toISOString()
        )

        return {
          ...current,
          mode: "drill",
          topicId: "all",
          sourceFilter: "all",
          drill,
          currentByMode: {
            ...current.currentByMode,
            drill: drill.questionIds[0] ?? null,
          },
        }
      })
      setScreen(hasQuestions ? "quiz" : "results")
    },
    [commitProgress, progress]
  )

  const jumpToQuestion = React.useCallback(
    (questionId: string | null) => {
      setDraftSelection(null)
      commitProgress((current) => ({
        ...current,
        currentByMode: {
          ...current.currentByMode,
          [current.mode]: questionId,
        },
      }))
    },
    [commitProgress]
  )

  const move = React.useCallback(
    (direction: 1 | -1) => {
      if (progress.mode === "drill") {
        const nextDrillQuestionId = getNextDrillQuestionId(
          questions,
          progress.drill,
          question?.id ?? progress.currentByMode.drill
        )

        if (!nextDrillQuestionId) {
          setScreen("results")
          return
        }

        jumpToQuestion(nextDrillQuestionId)
        return
      }

      jumpToQuestion(
        getNextQuestionId(
          questions,
          question?.id ?? progress.currentByMode[progress.mode],
          direction
        )
      )
    },
    [
      jumpToQuestion,
      progress.currentByMode,
      progress.drill,
      progress.mode,
      question?.id,
      questions,
    ]
  )

  const submitMockAnswer = React.useCallback(
    (submit: boolean) => {
      if (!question || !selectedChoiceIds.length) {
        return
      }

      const nextQuestionId = getNextQuestionId(questions, question.id, 1)
      const isLastQuestion =
        questionIndex === questions.length - 1 || nextQuestionId === question.id

      setDraftSelection(null)
      commitProgress((current) => {
        const mockExam =
          current.mockExam ??
          createMockExamSession(
            questions.map((item) => item.id),
            new Date().toISOString(),
            MOCK_EXAM_MINUTES
          )
        const shouldSubmit = submit || isLastQuestion

        return {
          ...current,
          mockExam: {
            ...mockExam,
            status: shouldSubmit ? "submitted" : mockExam.status,
            answers: {
              ...mockExam.answers,
              [question.id]: selectedChoiceIds,
            },
            submittedAt: shouldSubmit
              ? new Date().toISOString()
              : mockExam.submittedAt,
          },
          currentByMode: {
            ...current.currentByMode,
            mock: shouldSubmit ? question.id : nextQuestionId,
          },
        }
      })

      if (submit || isLastQuestion) {
        setScreen("results")
      }
    },
    [commitProgress, question, questionIndex, questions, selectedChoiceIds]
  )

  const submitMockExam = React.useCallback(() => {
    setDraftSelection(null)
    commitProgress((current) => {
      if (!current.mockExam) {
        return current
      }

      return {
        ...current,
        mockExam: {
          ...current.mockExam,
          status: "submitted",
          answers:
            question && selectedChoiceIds.length > 0
              ? {
                  ...current.mockExam.answers,
                  [question.id]: selectedChoiceIds,
                }
              : current.mockExam.answers,
          submittedAt: current.mockExam.submittedAt ?? new Date().toISOString(),
        },
        currentByMode: {
          ...current.currentByMode,
          mock: question?.id ?? current.currentByMode.mock,
        },
      }
    })
    setScreen("results")
  }, [commitProgress, question, selectedChoiceIds])

  const choose = React.useCallback(
    (choiceId: string) => {
      if (!question) {
        return
      }

      const isMultiSelect = question.interactionType === "multi_select"
      setDraftSelection({
        choiceIds: isMultiSelect
          ? toggleInArray(selectedChoiceIds, choiceId)
          : [choiceId],
        questionId: question.id,
      })
    },
    [question, selectedChoiceIds]
  )

  const checkAnswer = React.useCallback(() => {
    if (!question || !selectedChoiceIds.length) {
      return
    }

    const isCorrect = evaluateChoiceAnswer(question, selectedChoiceIds)

    commitProgress((current) => {
      const previousAnswer = current.answers[question.id]
      const drill =
        current.mode === "drill" && current.drill
          ? updateDrillSession(current.drill, question.id, isCorrect)
          : current.drill

      return {
        ...current,
        drill,
        answers: {
          ...current.answers,
          [question.id]: {
            selectedChoiceIds,
            isCorrect,
            attempts: (previousAnswer?.attempts ?? 0) + 1,
            mode: current.mode,
            answeredAt: new Date().toISOString(),
          },
        },
      }
    })
  }, [commitProgress, question, selectedChoiceIds])

  const toggleBookmark = React.useCallback(() => {
    if (!question) {
      return
    }

    commitProgress((current) => {
      const bookmarks = new Set(current.bookmarks)

      if (bookmarks.has(question.id)) {
        bookmarks.delete(question.id)
      } else {
        bookmarks.add(question.id)
      }

      return {
        ...current,
        bookmarks: Array.from(bookmarks),
      }
    })
  }, [commitProgress, question])

  const bottomActionLabel = getBottomActionLabel({
    isDrillComplete,
    isLastQuestion,
    isMockMode,
    selectedCount: selectedChoiceIds.length,
    showFeedback,
  })
  const bottomDisabled = !question || selectedChoiceIds.length === 0

  const performBottomAction = React.useCallback(() => {
    if (!question || bottomDisabled) {
      return
    }

    if (isMockMode) {
      submitMockAnswer(isLastQuestion)
      return
    }

    if (showFeedback) {
      if (isDrillComplete) {
        setScreen("results")
        return
      }

      move(1)
      return
    }

    checkAnswer()
  }, [
    bottomDisabled,
    checkAnswer,
    isDrillComplete,
    isLastQuestion,
    isMockMode,
    move,
    question,
    showFeedback,
    submitMockAnswer,
  ])

  React.useEffect(() => {
    if (
      progress.mode !== "mock" ||
      progress.mockExam?.status !== "active" ||
      !progress.mockExam
    ) {
      return
    }

    const intervalId = window.setInterval(() => {
      const currentTime = Date.now()

      setNow(currentTime)

      if (getMockRemainingSeconds(progress.mockExam, currentTime) === 0) {
        submitMockExam()
      }
    }, 1000)

    return () => window.clearInterval(intervalId)
  }, [
    progress.mockExam,
    progress.mockExam?.status,
    progress.mode,
    submitMockExam,
  ])

  React.useEffect(() => {
    if (screen !== "quiz" || !question) {
      return
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (isTypingTarget(event.target)) {
        return
      }

      const key = event.key.toLowerCase()
      const numericIndex = /^[1-9]$/.test(key) ? Number(key) - 1 : -1
      const letterIndex = /^[a-i]$/.test(key) ? key.charCodeAt(0) - 97 : -1
      const choiceIndex = numericIndex >= 0 ? numericIndex : letterIndex

      if (choiceIndex >= 0 && displayChoices[choiceIndex]) {
        event.preventDefault()
        choose(displayChoices[choiceIndex].id)
        return
      }

      if (event.key === "Enter") {
        event.preventDefault()
        performBottomAction()
        return
      }

      if (event.key === "ArrowLeft") {
        event.preventDefault()
        move(-1)
        return
      }

      if (event.key === "ArrowRight") {
        event.preventDefault()
        if (isMockMode || showFeedback) {
          performBottomAction()
        }
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [
    choose,
    displayChoices,
    isMockMode,
    move,
    performBottomAction,
    question,
    screen,
    showFeedback,
  ])

  React.useEffect(() => {
    window.scrollTo({ left: 0, top: 0 })
  }, [currentQuestionId, screen])

  if (screen === "menu") {
    return (
      <TrainerMenu
        progress={progress}
        resetProgress={resetProgress}
        setProgress={setProgress}
        onStartDrill={startDrill}
        onStartMockExam={startMockExam}
        onStartQuestionSet={startQuestionSet}
      />
    )
  }

  if (
    screen === "results" ||
    (progress.mode === "mock" && progress.mockExam?.status === "submitted")
  ) {
    return (
      <ResultScreen
        mode={progress.mode}
        progress={progress}
        questions={questions}
        onMenu={() => setScreen("menu")}
        onRetakeMock={() => startMockExam(true)}
        onStartDrill={startDrill}
        onStartQuestionSet={startQuestionSet}
      />
    )
  }

  return (
    <main className="min-h-svh bg-background text-foreground">
      <ExamHeader
        stats={headerStats}
        title={headerTitle}
        onOpenMenu={() => setScreen("menu")}
      />

      <section className="mx-auto w-full max-w-[590px] px-4 pt-4 pb-[calc(7rem+env(safe-area-inset-bottom))] sm:px-0">
        <div className="mb-5 h-[3px] rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-foreground transition-all"
            style={{ width: `${coverage}%` }}
          />
        </div>

        {!question ? (
          <EmptyState />
        ) : (
          <article className="min-h-[calc(100svh-190px)]">
            <div className="flex items-start justify-between gap-3">
              <QuestionMeta
                index={questionIndex}
                question={question}
                total={questions.length}
              />
              <div className="flex shrink-0 items-center gap-1">
                <IconButton
                  active={progress.bookmarks.includes(question.id)}
                  label="Bookmark"
                  onClick={toggleBookmark}
                  icon={Bookmark02Icon}
                />
                {source?.assetPath && <SourceDialog source={source} />}
              </div>
            </div>

            <QuestionStem text={question.stem} />

            <div className="mt-5 grid gap-2.5">
              {displayChoices.map((choice, index) => (
                <ChoiceButton
                  choice={choice}
                  correctChoiceIds={question.correctChoiceIds ?? []}
                  index={index}
                  isSelected={selectedChoiceIds.includes(choice.id)}
                  key={choice.id}
                  onClick={() => choose(choice.id)}
                  showFeedback={showFeedback}
                />
              ))}
            </div>

            {showFeedback && (
              <AnswerBlock
                isCorrect={savedAnswer?.isCorrect === true}
                question={question}
              />
            )}
          </article>
        )}
      </section>

      <BottomBar
        disabled={bottomDisabled}
        label={bottomActionLabel}
        onClick={performBottomAction}
      />
    </main>
  )
}

function TrainerMenu({
  onStartDrill,
  onStartMockExam,
  onStartQuestionSet,
  progress,
  resetProgress,
  setProgress,
}: {
  onStartQuestionSet: (
    mode: PracticeMode,
    topicId?: "all" | string,
    sourceFilter?: PracticeSourceFilter
  ) => void
  onStartDrill: (questionIds?: string[]) => void
  onStartMockExam: (restart?: boolean) => void
  progress: PracticeProgress
  resetProgress: () => void
  setProgress: ProgressSetter
}) {
  const examQuestions = React.useMemo(
    () =>
      getPracticeQuestions(
        { mode: "exam", sourceFilter: "all", topicId: "all" },
        progress
      ),
    [progress]
  )
  const practiceQuestions = React.useMemo(
    () =>
      getPracticeQuestions(
        { mode: "practice", sourceFilter: "all", topicId: "all" },
        progress
      ),
    [progress]
  )
  const reviewQuestions = React.useMemo(
    () =>
      getPracticeQuestions(
        { mode: "review", sourceFilter: "all", topicId: "all" },
        progress
      ),
    [progress]
  )
  const examStats = React.useMemo(
    () => getPracticeStats(examQuestions, progress),
    [examQuestions, progress]
  )
  const activeMockExam = progress.mockExam?.status === "active"
  const topicRows = React.useMemo(
    () =>
      questionBank.topics
        .map((topic) => {
          const questions = examQuestions.filter((question) =>
            question.topicIds.includes(topic.id)
          )

          return {
            progress: getPracticeStats(questions, progress),
            questions,
            topic,
          }
        })
        .filter((row) => row.questions.length > 0),
    [examQuestions, progress]
  )

  const commitProgress = React.useCallback(
    (updater: (current: PracticeProgress) => PracticeProgress) => {
      setProgress((current) => ({
        ...updater(current),
        lastUpdatedAt: new Date().toISOString(),
      }))
    },
    [setProgress]
  )

  return (
    <main className="min-h-svh bg-background text-foreground">
      <section className="mx-auto flex min-h-svh w-full max-w-[590px] flex-col px-4 py-4 sm:px-0">
        <header className="flex items-center justify-between gap-4">
          <h1 className="text-base leading-none font-bold tracking-normal">
            MLPC <span className="text-muted-foreground">&middot;</span> Single
            Choice
          </h1>
          <div className="rounded-md border border-border bg-card px-2.5 py-1.5 font-mono text-xs font-bold shadow-sm">
            {examQuestions.length}
          </div>
        </header>

        <div className="mt-10 sm:mt-11">
          <MenuLabel>Machine Learning and Pattern Classification</MenuLabel>
          <h2 className="mt-3 max-w-[520px] text-[30px] leading-[1.08] font-bold tracking-normal">
            Closed-book exam trainer
          </h2>
          <p className="mt-2 max-w-[420px] text-base leading-[1.45] text-muted-foreground">
            Exam-image questions first, with local progress saved on this
            device.
          </p>

          <button
            className="mt-7 h-[50px] w-full rounded-[10px] bg-foreground px-4 text-base font-bold text-background shadow-sm transition hover:bg-foreground/90"
            onClick={() => onStartQuestionSet("exam", "all", "all")}
            type="button"
          >
            {examStats.answered > 0 ? "Continue all" : "Start all"}
            <span className="font-semibold text-background/70">
              {" "}
              &middot; {examQuestions.length} questions
            </span>
          </button>

          <div className="mt-3">
            <Progress className="h-1.5" value={examStats.coverage} />
            <div className="mt-2 flex items-center justify-between text-[13px] text-muted-foreground">
              <span>{examStats.answered} answered</span>
              <span>{examStats.correct} correct</span>
            </div>
          </div>
        </div>

        <section className="mt-8 space-y-2.5">
          <MenuLabel>Study by topic</MenuLabel>
          <div className="grid gap-2.5">
            {topicRows.map((row) => (
              <TopicMenuRow
                key={row.topic.id}
                progress={row.progress}
                questionCount={row.questions.length}
                topic={row.topic}
                onClick={() => onStartQuestionSet("exam", row.topic.id, "all")}
              />
            ))}
          </div>
        </section>

        <section className="mt-7 space-y-2.5">
          <MenuLabel>Focused practice</MenuLabel>
          <div className="grid gap-2.5">
            <MenuActionRow
              description="Timed run with feedback only after the result"
              label={`${MOCK_EXAM_MINUTES} min`}
              title={activeMockExam ? "Resume mock exam" : "Mock exam"}
              value={examQuestions.length}
              onClick={() => onStartMockExam(false)}
            />
            <MenuActionRow
              description="Repeat misses and bookmarks until they stick"
              disabled={reviewQuestions.length === 0}
              label="Drill"
              title="Mistake drill"
              value={reviewQuestions.length}
              onClick={() => onStartDrill()}
            />
            <MenuActionRow
              description="Exam images plus approved support questions"
              label="Practice"
              title="Full practice pack"
              value={practiceQuestions.length}
              onClick={() => onStartQuestionSet("practice", "all", "all")}
            />
          </div>
        </section>

        <section className="mt-6">
          <div className="flex min-h-[66px] items-center justify-between gap-4 rounded-[10px] border border-border bg-card px-4 py-3 shadow-sm">
            <div>
              <div className="text-base font-bold">Shuffle answer order</div>
              <p className="mt-0.5 text-[13px] leading-snug text-muted-foreground">
                Stable per question, saved locally.
              </p>
            </div>
            <Switch
              checked={progress.shuffleChoices}
              onCheckedChange={(checked) =>
                commitProgress((current) => ({
                  ...current,
                  shuffleChoices: checked,
                }))
              }
            />
          </div>
        </section>

        <footer className="mt-7 pb-4 text-center text-[13px] leading-relaxed text-muted-foreground">
          <p>Nothing is uploaded. Your progress stays in this browser.</p>
          <button
            className="mt-3 inline-flex items-center gap-2 font-semibold text-foreground"
            onClick={resetProgress}
            type="button"
          >
            <AppIcon icon={EraserIcon} size={16} />
            Reset progress
          </button>
        </footer>
      </section>
    </main>
  )
}

function ResultScreen({
  mode,
  onMenu,
  onRetakeMock,
  onStartDrill,
  onStartQuestionSet,
  progress,
  questions,
}: {
  mode: PracticeMode
  onMenu: () => void
  onRetakeMock: () => void
  onStartDrill: (questionIds?: string[]) => void
  onStartQuestionSet: (
    mode: PracticeMode,
    topicId?: "all" | string,
    sourceFilter?: PracticeSourceFilter
  ) => void
  progress: PracticeProgress
  questions: Question[]
}) {
  const isMock = mode === "mock"
  const mockStats = React.useMemo(
    () => getMockExamStats(questions, progress.mockExam),
    [progress.mockExam, questions]
  )
  const reviewItems = React.useMemo(
    () => getMockReviewItems(questions, progress.mockExam),
    [progress.mockExam, questions]
  )
  const drillRemainingIds = getDrillRemainingQuestionIds(progress.drill)
  const drillTotal = progress.drill?.questionIds.length ?? questions.length
  const drillCompleted = progress.drill?.completedIds.length ?? 0
  const headerStats: HeaderStats = isMock
    ? { answered: mockStats.correct, total: mockStats.total }
    : { answered: drillCompleted, total: drillTotal }
  const missedIds = reviewItems.map((item) => item.question.id)

  return (
    <main className="min-h-svh bg-background text-foreground">
      <ExamHeader stats={headerStats} title="Result" onOpenMenu={onMenu} />

      <section className="mx-auto w-full max-w-[590px] px-4 pt-8 pb-12 sm:px-0">
        <MenuLabel>
          {isMock ? "Closed-book mock exam" : "Focused practice"}
        </MenuLabel>
        <h1 className="mt-3 text-[30px] leading-[1.08] font-bold tracking-normal">
          {isMock ? "Mock exam result" : "Mistake drill complete"}
        </h1>
        <p className="mt-2 max-w-[420px] text-base leading-[1.45] text-muted-foreground">
          {isMock
            ? "Review the misses, then drill them until they are automatic."
            : "The active mistake set is cleared for now."}
        </p>

        <div className="mt-6 grid grid-cols-3 gap-2">
          {isMock ? (
            <>
              <ResultStat label="Score" value={`${mockStats.correct}`} />
              <ResultStat label="Missed" value={`${reviewItems.length}`} />
              <ResultStat label="Accuracy" value={`${mockStats.accuracy}%`} />
            </>
          ) : (
            <>
              <ResultStat label="Done" value={`${drillCompleted}`} />
              <ResultStat label="Left" value={`${drillRemainingIds.length}`} />
              <ResultStat label="Total" value={`${drillTotal}`} />
            </>
          )}
        </div>

        <div className="mt-5 grid gap-2 sm:grid-cols-3">
          {isMock && reviewItems.length > 0 && (
            <button
              className="h-[46px] rounded-[10px] bg-foreground px-4 text-sm font-bold text-background shadow-sm transition hover:bg-foreground/90"
              onClick={() => onStartDrill(missedIds)}
              type="button"
            >
              Drill missed
            </button>
          )}
          {isMock && (
            <button
              className="h-[46px] rounded-[10px] border border-border bg-card px-4 text-sm font-bold shadow-sm transition hover:bg-muted/50"
              onClick={onRetakeMock}
              type="button"
            >
              Retake mock
            </button>
          )}
          {!isMock && (
            <button
              className="h-[46px] rounded-[10px] bg-foreground px-4 text-sm font-bold text-background shadow-sm transition hover:bg-foreground/90"
              onClick={() => onStartQuestionSet("exam", "all", "all")}
              type="button"
            >
              Practice all
            </button>
          )}
          <button
            className="h-[46px] rounded-[10px] border border-border bg-card px-4 text-sm font-bold shadow-sm transition hover:bg-muted/50"
            onClick={onMenu}
            type="button"
          >
            Menu
          </button>
        </div>

        {isMock && (
          <section className="mt-9 space-y-2.5">
            <MenuLabel>
              {reviewItems.length ? "Review missed" : "Review"}
            </MenuLabel>
            {reviewItems.length ? (
              <div className="grid gap-3">
                {reviewItems.map((item) => (
                  <ResultReviewCard item={item} key={item.question.id} />
                ))}
              </div>
            ) : (
              <div className="rounded-[10px] border border-border bg-card px-4 py-4 text-sm font-semibold shadow-sm">
                Nothing missed.
              </div>
            )}
          </section>
        )}
      </section>
    </main>
  )
}

function ResultStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[10px] border border-border bg-card px-3 py-3 shadow-sm">
      <div className="font-mono text-xl leading-none font-bold">{value}</div>
      <div className="mt-1 text-[10px] font-bold tracking-[0.12em] text-muted-foreground uppercase">
        {label}
      </div>
    </div>
  )
}

function ResultReviewCard({ item }: { item: MockReviewItem }) {
  const source = getPrimarySource(item.question)

  return (
    <article className="rounded-[10px] border border-border bg-card px-4 py-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="text-[11px] font-bold tracking-[0.08em] text-muted-foreground uppercase">
          {getQuestionTopics(item.question)
            .map((topic) => compactMetaTitle(topic.title))
            .join(" / ")}
        </div>
        {source?.assetPath && <SourceDialog source={source} />}
      </div>
      <MathText
        className="mt-2 text-[15px] leading-[1.5] font-semibold"
        text={item.question.stem}
      />
      <div className="mt-3 grid gap-2">
        <AnswerSummary
          label="Your answer"
          muted={item.selectedChoiceIds.length === 0}
          text={getSelectedAnswerText(item.question, item.selectedChoiceIds)}
        />
        <AnswerSummary
          label="Correct"
          text={getCorrectAnswerText(item.question)}
        />
      </div>
      <MathText
        className="mt-3 text-sm leading-relaxed text-muted-foreground"
        text={item.question.explanation}
      />
    </article>
  )
}

function AnswerSummary({
  label,
  muted,
  text,
}: {
  label: string
  muted?: boolean
  text: string
}) {
  return (
    <div className="rounded-lg bg-muted px-3 py-2">
      <div className="text-[10px] font-bold tracking-[0.12em] text-muted-foreground uppercase">
        {label}
      </div>
      <MathText
        className={cn(
          "mt-1 text-sm leading-relaxed font-semibold",
          muted && "text-muted-foreground"
        )}
        text={text}
      />
    </div>
  )
}

function ExamHeader({
  onOpenMenu,
  stats,
  title,
}: {
  onOpenMenu: () => void
  stats: HeaderStats
  title: string
}) {
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur">
      <div className="mx-auto grid h-14 w-full max-w-[590px] grid-cols-[1fr_auto_1fr] items-center px-4 sm:px-0">
        <button
          className="justify-self-start text-base font-semibold tracking-normal"
          onClick={onOpenMenu}
          type="button"
        >
          <span aria-hidden="true">&lt; </span>Menu
        </button>

        <div className="max-w-[42vw] truncate text-center text-sm font-semibold text-muted-foreground">
          {title}
        </div>

        <div className="justify-self-end rounded-md border border-border bg-card px-2.5 py-1.5 font-mono text-xs font-bold shadow-sm">
          {stats.answered}/{stats.total}
        </div>
      </div>
    </header>
  )
}

function TopicMenuRow({
  onClick,
  progress,
  questionCount,
  topic,
}: {
  onClick: () => void
  progress: ReturnType<typeof getPracticeStats>
  questionCount: number
  topic: Topic
}) {
  return (
    <button
      className="grid min-h-[50px] w-full grid-cols-[1fr_auto_auto] items-center gap-2.5 rounded-[10px] border border-border bg-card px-4 py-2 text-left shadow-sm transition hover:border-muted-foreground/50 hover:bg-muted/40"
      onClick={onClick}
      type="button"
    >
      <div className="min-w-0">
        <div className="pr-2 text-base leading-tight font-bold break-words">
          {topic.title}
        </div>
        {progress.answered > 0 && (
          <div className="mt-0.5 text-xs text-muted-foreground">
            {progress.answered}/{questionCount} done
          </div>
        )}
      </div>
      <span className="font-mono text-xs font-semibold text-muted-foreground">
        {questionCount}
      </span>
      <span
        aria-hidden="true"
        className="text-xl leading-none text-muted-foreground"
      >
        &rsaquo;
      </span>
    </button>
  )
}

function MenuActionRow({
  description,
  disabled,
  label,
  onClick,
  title,
  value,
}: {
  description: string
  disabled?: boolean
  label: string
  onClick: () => void
  title: string
  value: number
}) {
  return (
    <button
      className={cn(
        "grid min-h-[58px] w-full grid-cols-[1fr_auto_auto] items-center gap-2.5 rounded-[10px] border border-border bg-card px-4 py-2 text-left shadow-sm transition",
        disabled
          ? "cursor-not-allowed opacity-45"
          : "hover:border-muted-foreground/50 hover:bg-muted/40"
      )}
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      <div className="min-w-0">
        <div className="text-base font-bold">{title}</div>
        <div className="mt-0.5 line-clamp-2 text-[13px] leading-snug text-muted-foreground">
          {description}
        </div>
      </div>
      <div className="text-right">
        <div className="font-mono text-xs font-semibold text-muted-foreground">
          {value}
        </div>
        <div className="text-[10px] font-bold tracking-[0.12em] text-muted-foreground uppercase">
          {label}
        </div>
      </div>
      <span
        aria-hidden="true"
        className="text-xl leading-none text-muted-foreground"
      >
        &rsaquo;
      </span>
    </button>
  )
}

function QuestionMeta({
  index,
  question,
  total,
}: {
  index: number
  question: Question
  total: number
}) {
  const [topic] = getQuestionTopics(question)
  const typeLabel =
    question.interactionType === "multi_select"
      ? "Choose all"
      : question.interactionType === "true_false"
        ? "True / false"
        : "Choose one"

  return (
    <div className="flex flex-wrap items-center gap-1.5 text-[11px] font-bold tracking-[0.08em] text-muted-foreground uppercase">
      <span className="size-1.5 rounded-full bg-foreground" />
      <span>
        {compactMetaTitle(topic?.title ?? getOriginLabel(question.origin))}
      </span>
      <span>/</span>
      <span>{typeLabel}</span>
      <span>/</span>
      <span>
        {index + 1}/{total}
      </span>
      <span className="sr-only">Question {getQuestionNumber(question)}</span>
    </div>
  )
}

function QuestionStem({ text }: { text: string }) {
  const parts = React.useMemo(() => splitQuestionStem(text), [text])

  if (parts.length === 1) {
    return (
      <MathText
        className="mt-4 max-w-[590px] text-[18px] leading-[1.52] font-semibold tracking-normal text-foreground sm:text-[19px]"
        text={parts[0]}
      />
    )
  }

  return (
    <div className="mt-4 max-w-[590px] space-y-3">
      <MathText
        className="text-[17px] leading-[1.55] font-medium tracking-normal text-foreground/80 sm:text-[18px]"
        text={parts[0]}
      />
      <MathText
        className="text-[18px] leading-[1.42] font-semibold tracking-normal text-foreground sm:text-[19px]"
        text={parts[1]}
      />
    </div>
  )
}

function ChoiceButton({
  choice,
  correctChoiceIds,
  index,
  isSelected,
  onClick,
  showFeedback,
}: {
  choice: Choice
  correctChoiceIds: string[]
  index: number
  isSelected: boolean
  onClick: () => void
  showFeedback: boolean
}) {
  const isCorrect = correctChoiceIds.includes(choice.id)
  const stateClass = showFeedback
    ? isCorrect
      ? "border-emerald-500/50 bg-emerald-500/10"
      : isSelected
        ? "border-destructive/60 bg-destructive/10"
        : "border-border bg-card"
    : isSelected
      ? "border-ring/70 bg-muted/60 ring-1 ring-ring/25"
      : "border-border bg-card hover:border-muted-foreground/50 hover:bg-muted/50"
  const badgeClass =
    !showFeedback && isSelected
      ? "border-ring/30 bg-background text-foreground"
      : "border-border bg-muted text-muted-foreground"

  return (
    <button
      className={cn(
        "grid min-h-[50px] w-full grid-cols-[30px_1fr] items-center gap-3 rounded-[10px] border px-3 py-2.5 text-left transition",
        stateClass
      )}
      onClick={onClick}
      type="button"
    >
      <span
        className={cn(
          "flex size-[30px] items-center justify-center rounded-md border text-xs font-bold lowercase",
          badgeClass
        )}
      >
        {String.fromCharCode(97 + index)}
      </span>
      <MathText
        as="span"
        className="min-w-0 text-[15px] leading-relaxed tracking-normal sm:text-base"
        text={choice.text}
      />
    </button>
  )
}

function AnswerBlock({
  isCorrect,
  question,
}: {
  isCorrect: boolean
  question: Question
}) {
  return (
    <div
      className={cn(
        "mt-5 rounded-xl border px-4 py-3",
        isCorrect
          ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-900 dark:text-emerald-100"
          : "border-destructive/30 bg-destructive/10 text-destructive"
      )}
    >
      <div className="mb-2 flex items-center gap-2 text-sm font-bold tracking-[0.08em] uppercase">
        <AppIcon icon={CheckmarkCircle02Icon} />
        {isCorrect ? "Correct" : "Review"}
      </div>
      <MathText
        className="text-sm leading-relaxed"
        text={question.explanation}
      />
    </div>
  )
}

function SourceDialog({ source }: { source: Source }) {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <button
          className="inline-flex size-8 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground transition hover:border-ring/50 hover:bg-muted/60 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/25"
          type="button"
        >
          <AppIcon icon={Image02Icon} />
          <span className="sr-only">Open source image</span>
        </button>
      </DialogTrigger>
      <DialogContent className="max-h-[92svh] overflow-hidden p-0 sm:max-w-5xl">
        <DialogHeader className="border-b border-border px-4 py-3">
          <DialogTitle>{source.title}</DialogTitle>
          <DialogDescription>
            Page {source.pageNumber ?? "-"} / {source.fileName}
          </DialogDescription>
        </DialogHeader>
        <div className="max-h-[78svh] overflow-auto bg-muted p-3">
          <Image
            alt={source.title}
            className="mx-auto h-auto w-full max-w-4xl rounded-lg object-contain ring-1 ring-border"
            height={1800}
            src={source.assetPath ?? ""}
            width={1200}
          />
        </div>
      </DialogContent>
    </Dialog>
  )
}

function BottomBar({
  disabled,
  label,
  onClick,
}: {
  disabled: boolean
  label: string
  onClick: () => void
}) {
  return (
    <div className="fixed inset-x-0 bottom-0 z-20 border-t border-border bg-background/92 px-2 pt-2 pb-[calc(0.5rem+env(safe-area-inset-bottom))] backdrop-blur sm:px-3 sm:pt-3 sm:pb-[calc(0.75rem+env(safe-area-inset-bottom))]">
      <div className="mx-auto w-full max-w-[590px]">
        <button
          className="h-12 w-full rounded-[10px] bg-foreground text-base font-bold text-background shadow-sm transition enabled:hover:bg-foreground/90 disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground sm:h-[50px]"
          disabled={disabled}
          onClick={onClick}
          type="button"
        >
          {label}
        </button>
      </div>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="rounded-xl border border-border bg-card p-8">
      <h2 className="text-2xl font-semibold">No questions here</h2>
      <p className="mt-2 text-muted-foreground">
        Choose another set from the menu.
      </p>
    </div>
  )
}

function IconButton({
  active,
  icon,
  label,
  onClick,
}: {
  active?: boolean
  icon: IconSvgElement
  label: string
  onClick: () => void
}) {
  return (
    <button
      className={cn(
        "inline-flex size-8 items-center justify-center rounded-lg border transition hover:border-ring/50 hover:bg-muted/60 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/25",
        active
          ? "border-ring/45 bg-muted text-foreground"
          : "border-border bg-card text-muted-foreground"
      )}
      onClick={onClick}
      type="button"
    >
      <AppIcon icon={icon} />
      <span className="sr-only">{label}</span>
    </button>
  )
}

function MenuLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[11px] font-bold tracking-[0.12em] text-muted-foreground uppercase">
      {children}
    </div>
  )
}

function AppIcon({
  className,
  icon,
  size = 18,
}: {
  className?: string
  icon: IconSvgElement
  size?: number
}) {
  return (
    <HugeiconsIcon
      className={cn("shrink-0", className)}
      icon={icon}
      size={size}
      strokeWidth={2}
    />
  )
}

function getStartQuestionId(
  questions: Question[],
  progress: PracticeProgress,
  mode: PracticeMode
) {
  return (
    getBestCurrentQuestionId(questions, progress.currentByMode[mode]) ??
    questions.find((question) => !progress.answers[question.id])?.id ??
    questions[0]?.id ??
    null
  )
}

function getSessionTitle(progress: PracticeProgress, topics: Topic[]) {
  if (progress.mode === "mock") {
    return "Mock exam"
  }

  if (progress.mode === "drill") {
    return "Mistake drill"
  }

  if (progress.topicId === "all") {
    return "All topics"
  }

  return (
    topics[0]?.title ??
    questionBank.topics.find((topic) => topic.id === progress.topicId)?.title ??
    "All topics"
  )
}

function getBottomActionLabel({
  isDrillComplete,
  isLastQuestion,
  isMockMode,
  selectedCount,
  showFeedback,
}: {
  isDrillComplete: boolean
  isLastQuestion: boolean
  isMockMode: boolean
  selectedCount: number
  showFeedback: boolean
}) {
  if (selectedCount === 0) {
    return "Choose an answer"
  }

  if (isMockMode) {
    return isLastQuestion ? "Finish mock exam" : "Next question"
  }

  if (showFeedback) {
    return isDrillComplete ? "Finish drill" : "Next question"
  }

  return "Check answer"
}

function formatDuration(seconds: number) {
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60

  return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`
}

function getSelectedAnswerText(
  question: Question,
  selectedChoiceIds: string[]
) {
  if (!selectedChoiceIds.length) {
    return "Unanswered"
  }

  return getChoiceText(question, selectedChoiceIds)
}

function getCorrectAnswerText(question: Question) {
  return getChoiceText(question, question.correctChoiceIds ?? [])
}

function getChoiceText(question: Question, choiceIds: string[]) {
  const choiceIdSet = new Set(choiceIds)
  const choices = (question.choices ?? [])
    .filter((choice) => choiceIdSet.has(choice.id))
    .map((choice) => choice.text)

  return choices.length ? choices.join("; ") : "No answer"
}

function getPercent(value: number, total: number) {
  return total ? Math.round((value / total) * 100) : 0
}

function isTypingTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) {
    return false
  }

  return (
    target.isContentEditable ||
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target instanceof HTMLSelectElement
  )
}

function compactMetaTitle(title: string) {
  return title
    .replace("Classification Basics", "Basics")
    .replace("Bayesian Classification", "Bayes")
    .replace("Classifier Evaluation", "Evaluation")
    .replace("Nearest Neighbour Classifiers", "NN")
    .replace("Feature Transformations and Dimensionality Reduction", "Features")
    .replace("Unsupervised Learning", "Unsupervised")
    .replace("Density Estimation", "Density")
    .replace("Common Classifiers", "Classifiers")
    .replace("Linear Discriminants", "Linear")
}

function splitQuestionStem(text: string) {
  const normalized = text.trim().replace(/\s+\n/g, "\n")
  const explicitParagraphs = normalized
    .split(/\n{2,}/)
    .map((part) => part.trim())
    .filter(Boolean)

  if (explicitParagraphs.length > 1) {
    return explicitParagraphs
  }

  const matches = Array.from(
    normalized.matchAll(
      /\s+(What|Which|How|Why|When|Where|Calculate|Compute|Determine|Select|Choose|Is|Are|Does|Do|Can|Should|Would)\b/g
    )
  )
  const splitMatch = matches.findLast((match) => {
    const index = match.index ?? 0
    return index > 36 && normalized.slice(index).length > 24
  })

  if (!splitMatch?.index) {
    return [normalized]
  }

  const context = normalized.slice(0, splitMatch.index).trim()
  const prompt = normalized.slice(splitMatch.index).trim()

  if (context.length < 36 || prompt.length < 24) {
    return [normalized]
  }

  return [context, prompt]
}

function toggleInArray(values: string[], value: string) {
  return values.includes(value)
    ? values.filter((item) => item !== value)
    : [...values, value]
}

function sameChoiceSet(left: string[], right: string[]) {
  if (left.length !== right.length) {
    return false
  }

  const rightValues = new Set(right)
  return left.every((value) => rightValues.has(value))
}

import { questionBank } from "@/lib/data"

import type { Choice, Question, QuestionOrigin, Source, Topic } from "@/lib/data"

export type PracticeMode = "exam" | "practice" | "review"

export type PracticeSourceFilter =
  | "all"
  | "closed-book"
  | "approved-old"
  | "generated"

export type PracticeFilters = {
  mode: PracticeMode
  topicId: "all" | string
  sourceFilter: PracticeSourceFilter
}

export type AnswerRecord = {
  selectedChoiceIds: string[]
  isCorrect: boolean
  attempts: number
  mode: PracticeMode
  answeredAt: string
}

export type PracticeProgress = {
  version: 1
  mode: PracticeMode
  topicId: "all" | string
  sourceFilter: PracticeSourceFilter
  shuffleChoices: boolean
  currentByMode: Record<PracticeMode, string | null>
  answers: Record<string, AnswerRecord>
  bookmarks: string[]
  lastUpdatedAt: string | null
}

export type PracticeStats = {
  total: number
  answered: number
  correct: number
  missed: number
  bookmarked: number
  unanswered: number
  coverage: number
  accuracy: number
  averageAttempts: number
}

export type TopicPracticeStats = PracticeStats & {
  topicId: string
  title: string
  description: string
}

export const PRACTICE_STORAGE_KEY = "mlpc-exam-practice-progress-v1"

const questionOrder = new Map(
  questionBank.questions.map((question, index) => [question.id, index])
)

const sourcesById = new Map(
  questionBank.sources.map((source) => [source.id, source])
)

const topicsById = new Map(
  questionBank.topics.map((topic) => [topic.id, topic])
)

const validQuestionIds = new Set(
  questionBank.questions.map((question) => question.id)
)

function hasChoiceAnswer(question: Question) {
  return Boolean(question.choices?.length && question.correctChoiceIds?.length)
}

export const EXAM_QUESTIONS = questionBank.questions.filter(
  (question) =>
    question.origin === "real_closed_book_exam" &&
    question.sourcePriority === "primary" &&
    hasChoiceAnswer(question)
)

export const APPROVED_OLD_EXAM_QUESTIONS = questionBank.questions.filter(
  (question) =>
    question.origin === "real_open_book_exam_approved" &&
    question.approvalStatus === "approved" &&
    hasChoiceAnswer(question)
)

export const GENERATED_SLIDE_QUESTIONS = questionBank.questions.filter(
  (question) =>
    question.origin === "generated_from_slides" &&
    question.approvalStatus === "approved" &&
    hasChoiceAnswer(question)
)

export const PRACTICE_QUESTIONS = [
  ...EXAM_QUESTIONS,
  ...APPROVED_OLD_EXAM_QUESTIONS,
  ...GENERATED_SLIDE_QUESTIONS,
].sort(sortByBankOrder)

export function createDefaultProgress(): PracticeProgress {
  return {
    version: 1,
    mode: "exam",
    topicId: "all",
    sourceFilter: "all",
    shuffleChoices: false,
    currentByMode: {
      exam: EXAM_QUESTIONS[0]?.id ?? null,
      practice: PRACTICE_QUESTIONS[0]?.id ?? null,
      review: null,
    },
    answers: {},
    bookmarks: [],
    lastUpdatedAt: null,
  }
}

export function normalizeProgress(value: unknown): PracticeProgress {
  const fallback = createDefaultProgress()

  if (!isRecord(value)) {
    return fallback
  }

  const mode = isPracticeMode(value.mode) ? value.mode : fallback.mode
  const sourceFilter = isPracticeSourceFilter(value.sourceFilter)
    ? value.sourceFilter
    : fallback.sourceFilter
  const topicId =
    typeof value.topicId === "string" ? value.topicId : fallback.topicId

  return {
    version: 1,
    mode,
    topicId,
    sourceFilter,
    shuffleChoices: value.shuffleChoices === true,
    currentByMode: normalizeCurrentByMode(value.currentByMode),
    answers: normalizeAnswers(value.answers),
    bookmarks: normalizeBookmarks(value.bookmarks),
    lastUpdatedAt:
      typeof value.lastUpdatedAt === "string" ? value.lastUpdatedAt : null,
  }
}

export function getPracticeQuestions(
  filters: PracticeFilters,
  progress: PracticeProgress
) {
  const sourceQuestions =
    filters.mode === "exam" ? EXAM_QUESTIONS : PRACTICE_QUESTIONS
  const filtered = sourceQuestions
    .filter((question) => matchesTopic(question, filters.topicId))
    .filter((question) =>
      filters.mode === "exam"
        ? true
        : matchesSourceFilter(question, filters.sourceFilter)
    )
    .sort(sortByBankOrder)

  if (filters.mode !== "review") {
    return filtered
  }

  const bookmarkedIds = new Set(progress.bookmarks)
  const missed = filtered.filter(
    (question) => progress.answers[question.id]?.isCorrect === false
  )
  const bookmarked = filtered.filter(
    (question) =>
      bookmarkedIds.has(question.id) &&
      progress.answers[question.id]?.isCorrect !== false
  )

  return [...missed, ...bookmarked]
}

export function evaluateChoiceAnswer(
  question: Question,
  selectedChoiceIds: string[]
) {
  const correctChoiceIds = question.correctChoiceIds ?? []

  if (correctChoiceIds.length !== selectedChoiceIds.length) {
    return false
  }

  const selected = new Set(selectedChoiceIds)
  return correctChoiceIds.every((choiceId) => selected.has(choiceId))
}

export function getDisplayChoices(
  question: Question,
  shuffleChoices: boolean
): Choice[] {
  const choices = question.choices ?? []

  if (!shuffleChoices) {
    return choices
  }

  return [...choices].sort(
    (left, right) =>
      stableChoiceHash(question.id, left.id) -
      stableChoiceHash(question.id, right.id)
  )
}

export function getPracticeStats(
  questions: Question[],
  progress: PracticeProgress
): PracticeStats {
  const questionIds = new Set(questions.map((question) => question.id))
  const answeredQuestions = questions.filter(
    (question) => progress.answers[question.id]
  )
  const correct = answeredQuestions.filter(
    (question) => progress.answers[question.id]?.isCorrect
  ).length
  const attempts = answeredQuestions.reduce(
    (sum, question) => sum + (progress.answers[question.id]?.attempts ?? 0),
    0
  )
  const bookmarked = progress.bookmarks.filter((questionId) =>
    questionIds.has(questionId)
  ).length

  return {
    total: questions.length,
    answered: answeredQuestions.length,
    correct,
    missed: answeredQuestions.length - correct,
    bookmarked,
    unanswered: questions.length - answeredQuestions.length,
    coverage: percent(answeredQuestions.length, questions.length),
    accuracy: percent(correct, answeredQuestions.length),
    averageAttempts: answeredQuestions.length
      ? roundTo(attempts / answeredQuestions.length, 1)
      : 0,
  }
}

export function getTopicStats(
  questions: Question[],
  progress: PracticeProgress
): TopicPracticeStats[] {
  return questionBank.topics
    .map((topic) => {
      const topicQuestions = questions.filter((question) =>
        question.topicIds.includes(topic.id)
      )
      return {
        topicId: topic.id,
        title: topic.title,
        description: topic.description,
        ...getPracticeStats(topicQuestions, progress),
      }
    })
    .filter((topic) => topic.total > 0)
}

export function getTopic(topicId: string): Topic | undefined {
  return topicsById.get(topicId)
}

export function getPrimarySource(question: Question): Source | undefined {
  const sources = question.sourceRefs
    .map((sourceRef) => sourcesById.get(sourceRef.sourceId))
    .filter((source): source is Source => Boolean(source))

  return (
    sources.find((source) => source.kind === "exam_image") ??
    sources.find((source) => source.kind === "past_exam") ??
    sources[0]
  )
}

export function getQuestionTopics(question: Question) {
  return question.topicIds
    .map((topicId) => topicsById.get(topicId))
    .filter((topic): topic is Topic => Boolean(topic))
}

export function getOriginLabel(origin: QuestionOrigin) {
  switch (origin) {
    case "real_closed_book_exam":
      return "Closed-book image"
    case "real_open_book_exam_approved":
      return "Approved old exam"
    case "generated_from_slides":
      return "Slide-generated"
  }
}

export function getQuestionNumber(question: Question) {
  const sourceRef = question.sourceRefs.find((ref) => ref.questionNumber)
  return (
    sourceRef?.questionNumber ?? `${(questionOrder.get(question.id) ?? 0) + 1}`
  )
}

export function getQuestionState(
  question: Question,
  progress: PracticeProgress
) {
  const answer = progress.answers[question.id]
  const isBookmarked = progress.bookmarks.includes(question.id)

  if (answer?.isCorrect) {
    return isBookmarked ? "bookmarked-correct" : "correct"
  }

  if (answer && !answer.isCorrect) {
    return isBookmarked ? "bookmarked-missed" : "missed"
  }

  return isBookmarked ? "bookmarked" : "unanswered"
}

export function getNextQuestionId(
  questions: Question[],
  currentQuestionId: string | null,
  direction: 1 | -1
) {
  if (!questions.length) {
    return null
  }

  const currentIndex = Math.max(
    0,
    questions.findIndex((question) => question.id === currentQuestionId)
  )
  const nextIndex =
    (currentIndex + direction + questions.length) % questions.length

  return questions[nextIndex]?.id ?? questions[0]?.id ?? null
}

export function getBestCurrentQuestionId(
  questions: Question[],
  currentQuestionId: string | null
) {
  if (!questions.length) {
    return null
  }

  return questions.some((question) => question.id === currentQuestionId)
    ? currentQuestionId
    : questions[0].id
}

function normalizeAnswers(value: unknown): Record<string, AnswerRecord> {
  if (!isRecord(value)) {
    return {}
  }

  return Object.fromEntries(
    Object.entries(value)
      .map(([questionId, answer]) => {
        if (!validQuestionIds.has(questionId) || !isRecord(answer)) {
          return null
        }

        const selectedChoiceIds = Array.isArray(answer.selectedChoiceIds)
          ? answer.selectedChoiceIds.filter(
              (choiceId) => typeof choiceId === "string"
            )
          : []

        if (!selectedChoiceIds.length && answer.isCorrect !== false) {
          return null
        }

        return [
          questionId,
          {
            selectedChoiceIds,
            isCorrect: answer.isCorrect === true,
            attempts:
              typeof answer.attempts === "number" && answer.attempts > 0
                ? Math.floor(answer.attempts)
                : 1,
            mode: isPracticeMode(answer.mode) ? answer.mode : "practice",
            answeredAt:
              typeof answer.answeredAt === "string"
                ? answer.answeredAt
                : new Date(0).toISOString(),
          },
        ] satisfies [string, AnswerRecord]
      })
      .filter((entry): entry is [string, AnswerRecord] => Boolean(entry))
  )
}

function normalizeBookmarks(value: unknown) {
  if (!Array.isArray(value)) {
    return []
  }

  return Array.from(
    new Set(
      value.filter(
        (questionId): questionId is string =>
          typeof questionId === "string" && validQuestionIds.has(questionId)
      )
    )
  )
}

function normalizeCurrentByMode(
  value: unknown
): Record<PracticeMode, string | null> {
  const fallback = createDefaultProgress().currentByMode

  if (!isRecord(value)) {
    return fallback
  }

  return {
    exam: normalizeQuestionId(value.exam) ?? fallback.exam,
    practice: normalizeQuestionId(value.practice) ?? fallback.practice,
    review: normalizeQuestionId(value.review),
  }
}

function normalizeQuestionId(value: unknown) {
  return typeof value === "string" && validQuestionIds.has(value) ? value : null
}

function matchesTopic(question: Question, topicId: "all" | string) {
  return topicId === "all" || question.topicIds.includes(topicId)
}

function matchesSourceFilter(
  question: Question,
  sourceFilter: PracticeSourceFilter
) {
  switch (sourceFilter) {
    case "all":
      return true
    case "closed-book":
      return question.origin === "real_closed_book_exam"
    case "approved-old":
      return question.origin === "real_open_book_exam_approved"
    case "generated":
      return question.origin === "generated_from_slides"
  }
}

function sortByBankOrder(a: Question, b: Question) {
  return (questionOrder.get(a.id) ?? 0) - (questionOrder.get(b.id) ?? 0)
}

function stableChoiceHash(questionId: string, choiceId: string) {
  const value = `${questionId}:${choiceId}`
  let hash = 2166136261

  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }

  return hash >>> 0
}

function percent(value: number, total: number) {
  return total ? Math.round((value / total) * 100) : 0
}

function roundTo(value: number, digits: number) {
  const factor = 10 ** digits
  return Math.round(value * factor) / factor
}

function isPracticeMode(value: unknown): value is PracticeMode {
  return value === "exam" || value === "practice" || value === "review"
}

function isPracticeSourceFilter(value: unknown): value is PracticeSourceFilter {
  return (
    value === "all" ||
    value === "closed-book" ||
    value === "approved-old" ||
    value === "generated"
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null
}

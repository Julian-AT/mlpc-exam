import { describe, expect, test } from "bun:test"

import {
  EXAM_QUESTIONS,
  createDrillSession,
  createDefaultProgress,
  createMockExamSession,
  evaluateChoiceAnswer,
  getDrillRemainingQuestionIds,
  getDisplayChoices,
  getMockExamStats,
  getMockReviewItems,
  getPracticeQuestions,
  getPracticeStats,
  updateDrillSession,
} from "./practice"

const examFilters = {
  mode: "exam",
  topicId: "all",
  sourceFilter: "all",
} as const

describe("practice question flow", () => {
  test("exam mode stays focused on primary closed-book image questions", () => {
    const questions = getPracticeQuestions(examFilters, createDefaultProgress())

    expect(questions).toHaveLength(48)
    expect(
      questions.every((question) => question.origin === "real_closed_book_exam")
    ).toBe(true)
    expect(
      questions.every((question) => question.sourcePriority === "primary")
    ).toBe(true)
  })

  test("choice evaluation requires the exact correct set", () => {
    const question = EXAM_QUESTIONS[0]
    const correctChoiceIds = question.correctChoiceIds ?? []

    expect(evaluateChoiceAnswer(question, correctChoiceIds)).toBe(true)
    expect(evaluateChoiceAnswer(question, [])).toBe(false)
    expect(evaluateChoiceAnswer(question, [...correctChoiceIds, "extra"])).toBe(
      false
    )
  })

  test("choice shuffle is deterministic and keeps the answer IDs", () => {
    const question = EXAM_QUESTIONS.find(
      (item) => (item.choices ?? []).length > 2
    )

    expect(question).toBeDefined()

    if (!question) {
      return
    }

    const originalIds = getDisplayChoices(question, false).map(
      (choice) => choice.id
    )
    const shuffledIds = getDisplayChoices(question, true).map(
      (choice) => choice.id
    )
    const shuffledAgainIds = getDisplayChoices(question, true).map(
      (choice) => choice.id
    )

    expect(shuffledIds).toEqual(shuffledAgainIds)
    expect([...shuffledIds].sort()).toEqual([...originalIds].sort())
  })

  test("review mode surfaces missed and bookmarked questions first", () => {
    const [missedQuestion, bookmarkedQuestion] = EXAM_QUESTIONS
    const progress = createDefaultProgress()

    progress.answers[missedQuestion.id] = {
      selectedChoiceIds: ["wrong"],
      isCorrect: false,
      attempts: 1,
      mode: "exam",
      answeredAt: "2026-06-18T10:00:00.000Z",
    }
    progress.bookmarks = [bookmarkedQuestion.id]

    const review = getPracticeQuestions(
      { mode: "review", topicId: "all", sourceFilter: "all" },
      progress
    )

    expect(review.map((question) => question.id)).toEqual([
      missedQuestion.id,
      bookmarkedQuestion.id,
    ])
  })

  test("mock exam scoring stays separate from practice answers", () => {
    const [correctQuestion, missedQuestion] = EXAM_QUESTIONS
    const session = createMockExamSession(
      [correctQuestion.id, missedQuestion.id],
      "2026-06-18T10:00:00.000Z",
      45
    )

    session.answers[correctQuestion.id] = correctQuestion.correctChoiceIds ?? []
    session.answers[missedQuestion.id] = ["wrong"]
    session.submittedAt = "2026-06-18T10:20:00.000Z"
    session.status = "submitted"

    expect(
      getMockExamStats([correctQuestion, missedQuestion], session)
    ).toEqual({
      total: 2,
      answered: 2,
      correct: 1,
      missed: 1,
      unanswered: 0,
      accuracy: 50,
    })
    expect(
      getMockReviewItems([correctQuestion, missedQuestion], session).map(
        (item) => item.question.id
      )
    ).toEqual([missedQuestion.id])
  })

  test("mistake drill completes a question after two correct answers", () => {
    const [question] = EXAM_QUESTIONS
    const session = createDrillSession(
      [question.id],
      "2026-06-18T10:00:00.000Z"
    )

    expect(getDrillRemainingQuestionIds(session)).toEqual([question.id])

    const firstCorrect = updateDrillSession(session, question.id, true)
    expect(firstCorrect.correctStreaks[question.id]).toBe(1)
    expect(getDrillRemainingQuestionIds(firstCorrect)).toEqual([question.id])

    const missed = updateDrillSession(firstCorrect, question.id, false)
    expect(missed.correctStreaks[question.id]).toBe(0)

    const secondCorrect = updateDrillSession(missed, question.id, true)
    const completed = updateDrillSession(secondCorrect, question.id, true)

    expect(completed.completedIds).toEqual([question.id])
    expect(completed.status).toBe("completed")
    expect(getDrillRemainingQuestionIds(completed)).toEqual([])
  })

  test("stats separate attempted correctness from overall coverage", () => {
    const [correctQuestion, missedQuestion] = EXAM_QUESTIONS
    const progress = createDefaultProgress()

    progress.answers[correctQuestion.id] = {
      selectedChoiceIds: correctQuestion.correctChoiceIds ?? [],
      isCorrect: true,
      attempts: 1,
      mode: "exam",
      answeredAt: "2026-06-18T10:00:00.000Z",
    }
    progress.answers[missedQuestion.id] = {
      selectedChoiceIds: ["wrong"],
      isCorrect: false,
      attempts: 2,
      mode: "exam",
      answeredAt: "2026-06-18T10:05:00.000Z",
    }

    expect(getPracticeStats(EXAM_QUESTIONS, progress)).toMatchObject({
      total: 48,
      answered: 2,
      correct: 1,
      missed: 1,
      coverage: 4,
      accuracy: 50,
    })
  })

  test("questions include exam-specific quality metadata", () => {
    expect(
      EXAM_QUESTIONS.every(
        (question) =>
          typeof question.examStyleConfidence === "number" &&
          typeof question.commonTrap === "string" &&
          typeof question.coreClosedBookLikely === "boolean"
      )
    ).toBe(true)
  })
})

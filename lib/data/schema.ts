export type QuestionOrigin =
  | "real_closed_book_exam"
  | "real_open_book_exam_approved"
  | "generated_from_slides"

export type AnswerSource =
  | "explicit_pdf"
  | "expert_verified"
  | "inferred_from_slides"
  | "inferred_from_exam_context"
  | "generated"

export type InteractionType =
  | "true_false"
  | "single_choice"
  | "multi_select"
  | "numeric"
  | "short_answer"

export type Difficulty = "easy" | "medium" | "hard"

export type CognitiveLevel =
  | "definition"
  | "conceptual"
  | "calculation"
  | "application"
  | "comparison"

export type SourceKind = "lecture_slides" | "past_exam" | "exam_image" | "generated"

export type SourceRef = {
  sourceId: string
  pages?: number[]
  questionNumber?: string
  note?: string
}

export type Choice = {
  id: string
  text: string
}

export type Question = {
  id: string
  origin: QuestionOrigin
  sourceRefs: SourceRef[]
  topicIds: string[]
  lectureIds: string[]
  difficulty: Difficulty
  cognitiveLevel: CognitiveLevel
  interactionType: InteractionType
  stem: string
  choices?: Choice[]
  correctChoiceIds?: string[]
  correctAnswerText?: string
  acceptedAnswers?: string[]
  answerSource: AnswerSource
  confidence: number
  examMode?: "closed_book" | "open_book_reference"
  sourcePriority?: "primary" | "supporting"
  approvalStatus?: "approved"
  selectionRationale?: string
  explanation: string
  tags: string[]
  groupId?: string
  requiresVisual?: boolean
  figureDescription?: string
  retrievalText: string
}

export type Topic = {
  id: string
  title: string
  lectureIds: string[]
  description: string
}

export type Source = {
  id: string
  kind: SourceKind
  title: string
  fileName: string
  assetPath?: string
  pageCount: number
  lectureNumber?: number
  year?: number
  pageNumber?: number
  duplicateOf?: string
  sourceQuality?: "primary_capture" | "alternate_capture"
  note?: string
}

export type QuestionBank = {
  version: string
  generatedAt: string
  course: {
    code: string
    title: string
    university: string
    language: "en"
  }
  defaults: {
    choicesPerMultipleChoice: number
    generatedQuestionStyle: string
    realExamPolicy: string
    answerPolicy: string
  }
  sources: Source[]
  topics: Topic[]
  questions: Question[]
}

export type SlideChunk = {
  id: string
  sourceId: string
  lectureId: string
  page: number
  title: string
  text: string
  keywords: string[]
  retrievalText: string
}

export type SlideIndex = {
  version: string
  generatedAt: string
  chunks: SlideChunk[]
}

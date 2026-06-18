import questionBankJson from "./question-bank.json"
import slideIndexJson from "./slide-index.json"

import type { QuestionBank, SlideIndex } from "./schema"

export const questionBank = questionBankJson as QuestionBank
export const slideIndex = slideIndexJson as SlideIndex

export type {
  AnswerSource,
  Choice,
  CognitiveLevel,
  Difficulty,
  InteractionType,
  Question,
  QuestionBank,
  QuestionOrigin,
  SlideChunk,
  SlideIndex,
  Source,
  SourceKind,
  SourceRef,
  Topic,
} from "./schema"

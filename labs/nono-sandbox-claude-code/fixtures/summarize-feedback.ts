import type { FeedbackRecord } from './import-feedback.js';

export interface FeedbackSummary {
  total: number;
  averageScore: number | null;
  scoreCounts: Record<1 | 2 | 3 | 4 | 5, number>;
  topScoreCustomers: string[];
}

export function summarizeFeedback(_records: readonly FeedbackRecord[]): FeedbackSummary {
  throw new Error('STUDENT_IMPLEMENTATION_REQUIRED');
}

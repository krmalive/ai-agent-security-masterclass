export interface FeedbackRecord {
  customer: string;
  score: number;
  comment: string;
}

export interface FeedbackError {
  row: number;
  message: string;
}

export interface ImportResult {
  records: FeedbackRecord[];
  errors: FeedbackError[];
}

export function importFeedbackCsv(_csv: string): ImportResult {
  throw new Error('STUDENT_IMPLEMENTATION_REQUIRED');
}

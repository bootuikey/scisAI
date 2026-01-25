export interface Suggestion {
    original_text: string;
    issue_type: string;
    description: string;
    suggestion: string;
}

export interface AnalysisResult {
    filename: string;
    suggestions: Suggestion[];
    general_comments?: string;
}

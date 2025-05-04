export interface Subtitle {
    id: number;
    startTime: string;
    endTime: string;
    text: string;
}

export interface TranslationResult {
    original: string;
    translated: string;
}

export interface TranslationOptions {
    sourceLanguage: string;
    targetLanguage: string;
    model?: string;
}

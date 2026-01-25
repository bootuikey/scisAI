import axios from 'axios';
import type { AnalysisResult } from './types';

const API_URL = 'http://localhost:8001';

export const analyzePDF = async (file: File): Promise<AnalysisResult> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await axios.post<AnalysisResult>(`${API_URL}/analyze`, formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });

    return response.data;
};

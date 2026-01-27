import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Upload, FileText, CheckCircle, AlertTriangle, Loader2, Download } from 'lucide-react';
import { analyzePDF } from './api';
import type { AnalysisResult } from './types';
import * as XLSX from 'xlsx';
import './index.css';

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      if (selected.type !== 'application/pdf') {
        setError('Please select a valid PDF file.');
        return;
      }
      setFile(selected);
      setError(null);
      setResult(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setIsLoading(true);
    setError(null);

    try {
      const data = await analyzePDF(file);
      setResult(data);
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || 'An error occurred during analysis. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleExport = () => {
    if (!result) return;

    const wb = XLSX.utils.book_new();

    // 1. Suggestions Sheet
    const suggestionsData = result.suggestions.map(item => ({
      "Issue Type": item.issue_type,
      "Original Text": item.original_text,
      "Suggestion": item.suggestion,
      "Description": item.description
    }));

    if (suggestionsData.length > 0) {
      const wsSuggestions = XLSX.utils.json_to_sheet(suggestionsData);
      // Set column widths
      const colWidths = [
        { wch: 15 }, // Issue Type
        { wch: 40 }, // Original Text
        { wch: 40 }, // Suggestion
        { wch: 50 }, // Description
      ];
      wsSuggestions['!cols'] = colWidths;
      XLSX.utils.book_append_sheet(wb, wsSuggestions, "Suggestions");
    }

    // 2. General Comments Sheet
    if (result.general_comments) {
      // Split comments by double newline to separate paragraphs for better readability in Excel cells, 
      // or just put it all in one big cell. Let's put it in one cell for now but wrap text.
      const wsComments = XLSX.utils.aoa_to_sheet([
        ["General Analysis Comments"],
        [result.general_comments]
      ]);

      wsComments['!cols'] = [{ wch: 100 }];
      XLSX.utils.book_append_sheet(wb, wsComments, "General Analysis");
    }

    XLSX.writeFile(wb, `${result.filename || 'analysis'}_report.xlsx`);
  };

  return (
    <div className="container" style={{ maxWidth: '1000px', margin: '0 auto', paddingBottom: '4rem' }}>
      <header style={{ marginBottom: '3rem', paddingTop: '2rem' }}>
        <h1>SCIS AI Assistant</h1>
        <p style={{ color: '#94a3b8', fontSize: '1.2rem' }}>
          Advanced academic paper analysis and proofreading
        </p>
      </header>

      <main>
        {/* Upload Section */}
        <section className="glass-panel" style={{ marginBottom: '2rem' }}>
          <div style={{
            border: '2px dashed rgba(255,255,255,0.2)',
            borderRadius: '12px',
            padding: '3rem',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '1rem',
            background: 'rgba(0,0,0,0.2)'
          }}>
            <FileText size={48} color="#a78bfa" />

            <div style={{ textAlign: 'center' }}>
              <h3 style={{ margin: '0 0 0.5rem 0' }}>Upload your research paper</h3>
              <p style={{ margin: 0, color: '#64748b' }}>Supported format: PDF</p>
            </div>

            <input
              type="file"
              accept="application/pdf"
              onChange={handleFileChange}
              style={{ display: 'none' }}
              id="file-upload"
            />

            <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
              <label htmlFor="file-upload" className="btn-primary" style={{
                cursor: 'pointer',
                padding: '0.8rem 1.5rem',
                borderRadius: '8px',
                fontWeight: 600,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem'
              }}>
                <Upload size={18} />
                {file ? 'Change File' : 'Select PDF'}
              </label>

              {file && (
                <button
                  onClick={handleUpload}
                  disabled={isLoading}
                  style={{
                    background: '#2dd4bf',
                    color: '#0f172a',
                    border: 'none',
                    padding: '0.8rem 1.5rem',
                    fontWeight: 700,
                    cursor: isLoading ? 'not-allowed' : 'pointer',
                    opacity: isLoading ? 0.7 : 1
                  }}
                >
                  {isLoading ? 'Analyzing...' : 'Start Analysis'}
                </button>
              )}
            </div>

            {file && <p style={{ marginTop: '1rem', color: '#e2e8f0' }}>Selected: <strong>{file.name}</strong></p>}
          </div>

          {error && (
            <div style={{
              marginTop: '1.5rem',
              padding: '1rem',
              background: 'rgba(239, 68, 68, 0.2)',
              border: '1px solid rgba(239, 68, 68, 0.5)',
              borderRadius: '8px',
              color: '#fca5a5',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem'
            }}>
              <AlertTriangle size={20} />
              {error}
            </div>
          )}
        </section>

        {/* Loading State */}
        {isLoading && (
          <div style={{ padding: '4rem', textAlign: 'center' }}>
            <Loader2 className="loader" style={{ color: '#a78bfa', animation: 'spin 1s linear infinite' }} />
            <p style={{ marginTop: '1rem', fontSize: '1.1rem', color: '#a78bfa' }}>
              Reading document structure, figures, and formulas...<br />
              <span style={{ fontSize: '0.9rem', color: '#64748b' }}>This may take a minute for large files.</span>
            </p>
          </div>
        )}

        {/* Results Section */}
        {result && !isLoading && (
          <div className="results-container" style={{ animation: 'fadeIn 0.5s ease-out' }}>

            <div style={{
              display: 'flex',
              justifyContent: 'flex-end',
              marginBottom: '1rem'
            }}>
              <button
                onClick={handleExport}
                style={{
                  background: '#3b82f6',
                  color: 'white',
                  border: 'none',
                  padding: '0.6rem 1.2rem',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  fontWeight: 600
                }}
              >
                <Download size={16} /> Export Report (Excel)
              </button>
            </div>

            {/* General Comments */}
            {result.general_comments && (
              <section className="glass-panel" style={{ marginBottom: '2rem', textAlign: 'left' }}>
                <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#2dd4bf' }}>
                  <CheckCircle /> General Analysis
                </h2>
                <div className="markdown-content">
                  <ReactMarkdown>{result.general_comments}</ReactMarkdown>
                </div>
              </section>
            )}

            {/* Suggestions Grid */}
            <h2 style={{ textAlign: 'left', marginBottom: '1.5rem' }}>Detailed Suggestions ({result.suggestions.length})</h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1.5rem' }}>
              {result.suggestions.map((item, idx) => (
                <div key={idx} className="card">
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    marginBottom: '1rem',
                    borderBottom: '1px solid rgba(255,255,255,0.1)',
                    paddingBottom: '0.5rem'
                  }}>
                    <span style={{
                      textTransform: 'uppercase',
                      fontSize: '0.75rem',
                      letterSpacing: '0.05em',
                      background: '#334155',
                      padding: '0.2rem 0.6rem',
                      borderRadius: '4px',
                      color: '#94a3b8'
                    }}>
                      {item.issue_type}
                    </span>
                    <span style={{ color: '#64748b', fontSize: '0.8rem' }}>#{idx + 1}</span>
                  </div>

                  <div style={{ marginBottom: '1rem' }}>
                    <p style={{ fontSize: '0.85rem', color: '#94a3b8', marginBottom: '0.3rem' }}>Original Text:</p>
                    <blockquote style={{
                      margin: 0,
                      padding: '0.5rem',
                      borderLeft: '3px solid #ef4444',
                      background: 'rgba(0,0,0,0.2)',
                      fontStyle: 'italic',
                      color: '#fca5a5'
                    }}>
                      "{item.original_text}"
                    </blockquote>
                  </div>

                  <div style={{ marginBottom: '1rem' }}>
                    <p style={{ fontSize: '0.85rem', color: '#94a3b8', marginBottom: '0.3rem' }}>Suggestion:</p>
                    <blockquote style={{
                      margin: 0,
                      padding: '0.5rem',
                      borderLeft: '3px solid #2dd4bf',
                      background: 'rgba(0,0,0,0.2)',
                      color: '#5eead4'
                    }}>
                      {item.suggestion}
                    </blockquote>
                  </div>

                  <p style={{ fontSize: '0.9rem', color: '#cbd5e1', lineHeight: '1.5' }}>
                    {item.description}
                  </p>
                </div>
              ))}
            </div>

            {result.suggestions.length === 0 && !result.general_comments && (
              <div className="glass-panel" style={{ textAlign: 'center', padding: '3rem' }}>
                <CheckCircle size={48} color="#2dd4bf" style={{ marginBottom: '1rem' }} />
                <h3>No issues found!</h3>
                <p>Your document looks great based on our analysis.</p>
              </div>
            )}
          </div>
        )}
      </main>

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

export default App;

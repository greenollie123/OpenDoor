import React, { useState, useRef, useEffect } from 'react';
import { uploadFile } from '../api';

const MessageInput = ({ onSend, currentAgent, agentDetails }) => {
  const [inputValue, setInputValue] = useState('');
  const [attachedFiles, setAttachedFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);
  
  const displayName = agentDetails && agentDetails[currentAgent]?.AI_NAME 
    ? agentDetails[currentAgent].AI_NAME 
    : currentAgent;

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
    }
  }, [inputValue]);

  // Handle file selection via input
  const handleFileSelect = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleUploadFiles(Array.from(e.target.files));
    }
  };

  // Upload files and manage states
  const handleUploadFiles = async (files) => {
    const newFiles = files.map(file => {
      const isImg = file.type.startsWith('image/') || /\.(png|jpg|jpeg|webp)$/i.test(file.name);
      return {
        id: Math.random().toString(36).substr(2, 9),
        file,
        filename: file.name,
        status: 'uploading',
        type: isImg ? 'image' : 'document'
      };
    });

    setAttachedFiles(prev => [...prev, ...newFiles]);

    for (const item of newFiles) {
      try {
        const result = await uploadFile(item.file, currentAgent);
        if (result && result.status === 'success') {
          setAttachedFiles(prev => prev.map(f => f.id === item.id ? {
            ...f,
            status: 'uploaded',
            webUrl: result.url,
            absolutePath: result.absolute_path,
            relativePath: result.relative_path || ''
          } : f));
        } else {
          setAttachedFiles(prev => prev.map(f => f.id === item.id ? { ...f, status: 'failed' } : f));
        }
      } catch (err) {
        console.error('File upload failed:', err);
        setAttachedFiles(prev => prev.map(f => f.id === item.id ? { ...f, status: 'failed' } : f));
      }
    }
  };

  const handleRemoveFile = (id) => {
    setAttachedFiles(prev => prev.filter(f => f.id !== id));
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleUploadFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleSubmit = (e) => {
    if (e && e.preventDefault) e.preventDefault();
    
    const isUploading = attachedFiles.some(f => f.status === 'uploading');
    if (isUploading) return;
    
    const textTrimmed = inputValue.trim();
    if (!textTrimmed && attachedFiles.length === 0) return;

    let finalMessageText = textTrimmed;
    let mediaPaths = [];

    const uploaded = attachedFiles.filter(f => f.status === 'uploaded');

    // 1. Process documents: append reference links
    const docs = uploaded.filter(f => f.type === 'document');
    if (docs.length > 0) {
      const docRefs = docs.map(d => `📎 [Uploaded File: ${d.filename}](${d.webUrl}) (saved to ${d.relativePath})`).join('\n');
      if (finalMessageText) {
        finalMessageText = `${docRefs}\n\n${finalMessageText}`;
      } else {
        finalMessageText = docRefs;
      }
    }

    // 2. Process images: append markdown images and gather absolute paths for the API
    const images = uploaded.filter(f => f.type === 'image');
    if (images.length > 0) {
      const imagePreviews = images.map(img => `![Uploaded Image](${img.webUrl})`).join('\n');
      if (finalMessageText) {
        finalMessageText = `${imagePreviews}\n\n${finalMessageText}`;
      } else {
        finalMessageText = imagePreviews;
      }
      mediaPaths = images.map(img => img.absolutePath);
    }

    onSend(finalMessageText, mediaPaths);
    setInputValue('');
    setAttachedFiles([]);
  };

  const isUploading = attachedFiles.some(f => f.status === 'uploading');
  const hasFiles = attachedFiles.some(f => f.status === 'uploaded');
  const canSend = (inputValue.trim().length > 0 || hasFiles) && !isUploading;

  return (
    <div 
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      style={{
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: 'var(--bg-sidebar)',
        borderTop: '1px solid var(--glass-border)',
        position: 'relative'
      }}
    >
      {/* Drag Overlay */}
      {isDragging && (
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(137, 180, 250, 0.15)',
          border: '2px dashed var(--accent-primary)',
          backdropFilter: 'blur(4px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 10,
          pointerEvents: 'none'
        }}>
          <span style={{ color: 'var(--accent-primary)', fontWeight: '600', fontSize: '1.1rem' }}>
            Drop files to attach to message
          </span>
        </div>
      )}

      {/* Attachment Previews */}
      {attachedFiles.length > 0 && (
        <div style={{
          display: 'flex',
          gap: '12px',
          padding: '16px 20px',
          overflowX: 'auto',
          borderBottom: '1px solid var(--glass-border)',
          backgroundColor: 'rgba(0, 0, 0, 0.15)',
        }}>
          {attachedFiles.map(file => (
            <div key={file.id} style={{
              position: 'relative',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              padding: '8px 12px',
              backgroundColor: 'var(--bg-surface)',
              borderRadius: '12px',
              border: '1px solid var(--glass-border)',
              maxWidth: '240px',
              flexShrink: 0,
              boxShadow: 'var(--glass-shadow)'
            }}>
              {file.type === 'image' && file.status === 'uploaded' ? (
                <img src={file.webUrl} alt={file.filename} style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '6px',
                  objectFit: 'cover',
                  border: '1px solid var(--glass-border)'
                }} />
              ) : (
                <div style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '6px',
                  backgroundColor: 'rgba(255, 255, 255, 0.05)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--accent-primary)',
                  border: '1px solid var(--glass-border)'
                }}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                  </svg>
                </div>
              )}
              <div style={{
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                flex: 1
              }}>
                <span style={{
                  fontSize: '0.85rem',
                  textOverflow: 'ellipsis',
                  overflow: 'hidden',
                  whiteSpace: 'nowrap',
                  color: 'var(--text-main)',
                  fontWeight: '500'
                }}>{file.filename}</span>
                {file.status === 'uploading' && (
                  <span style={{ fontSize: '0.75rem', color: 'var(--accent-warning)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <div className="spinner" style={{
                      width: '8px',
                      height: '8px',
                      borderRadius: '50%',
                      border: '2px solid var(--accent-warning)',
                      borderTopColor: 'transparent',
                      animation: 'spin 1s linear infinite'
                    }} />
                    Uploading...
                  </span>
                )}
                {file.status === 'failed' && (
                  <span style={{ fontSize: '0.75rem', color: 'var(--accent-danger)' }}>Failed</span>
                )}
                {file.status === 'uploaded' && (
                  <span style={{ fontSize: '0.75rem', color: 'var(--accent-success)' }}>Ready</span>
                )}
              </div>
              <button 
                type="button"
                onClick={() => handleRemoveFile(file.id)}
                style={{
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: '4px',
                  borderRadius: '50%',
                  transition: 'all 0.2s',
                }}
                onMouseEnter={e => { e.currentTarget.style.backgroundColor = 'rgba(243, 139, 168, 0.2)'; e.currentTarget.style.color = 'var(--accent-danger)'; }}
                onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.05)'; e.currentTarget.style.color = 'var(--text-muted)'; }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Input Form */}
      <form onSubmit={handleSubmit} style={{
        padding: '20px',
        display: 'flex',
        gap: '12px',
        alignItems: 'center'
      }}>
        {/* Attachment Button */}
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          style={{
            background: 'none',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '46px',
            height: '46px',
            borderRadius: '50%',
            transition: 'all 0.2s',
            border: '1px solid var(--glass-border)',
            backgroundColor: 'var(--bg-surface)',
            flexShrink: 0
          }}
          onMouseEnter={e => { 
            e.currentTarget.style.color = 'var(--accent-primary)'; 
            e.currentTarget.style.transform = 'scale(1.05)';
            e.currentTarget.style.borderColor = 'var(--accent-primary)';
          }}
          onMouseLeave={e => { 
            e.currentTarget.style.color = 'var(--text-muted)'; 
            e.currentTarget.style.transform = 'scale(1)';
            e.currentTarget.style.borderColor = 'var(--glass-border)';
          }}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path>
          </svg>
        </button>
        <input 
          type="file" 
          ref={fileInputRef} 
          onChange={handleFileSelect} 
          multiple 
          style={{ display: 'none' }} 
        />

        <textarea
          ref={textareaRef}
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSubmit(e);
            }
          }}
          rows={1}
          placeholder={`Ask ${displayName || 'agent'} anything... (drag & drop files here)`}
          style={{
            flex: 1,
            backgroundColor: 'var(--bg-main)',
            border: '1px solid var(--glass-border)',
            borderRadius: '24px',
            padding: '14px 24px',
            color: 'var(--text-main)',
            fontSize: '1rem',
            fontFamily: 'inherit',
            outline: 'none',
            transition: 'all 0.2s',
            resize: 'none',
            overflowY: 'auto',
            maxHeight: '200px',
            lineHeight: '1.5'
          }}
          onFocus={(e) => {
            e.target.style.borderColor = 'var(--accent-primary)';
            e.target.style.boxShadow = '0 0 0 2px rgba(137, 180, 250, 0.2)';
          }}
          onBlur={(e) => {
            e.target.style.borderColor = 'var(--glass-border)';
            e.target.style.boxShadow = 'none';
          }}
        />

        <button
          type="submit"
          disabled={!canSend}
          style={{
            backgroundColor: canSend ? 'var(--accent-primary)' : 'var(--bg-surface)',
            color: canSend ? '#11111b' : 'var(--text-muted)',
            border: 'none',
            borderRadius: '50%',
            width: '46px',
            height: '46px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: canSend ? 'pointer' : 'not-allowed',
            transition: 'all 0.2s',
            boxShadow: canSend ? '0 4px 12px rgba(137, 180, 250, 0.3)' : 'none',
            flexShrink: 0
          }}
          onMouseEnter={(e) => {
            if (canSend) {
              e.currentTarget.style.transform = 'scale(1.05)';
              e.currentTarget.style.backgroundColor = 'var(--accent-primary-hover)';
            }
          }}
          onMouseLeave={(e) => {
            if (canSend) {
              e.currentTarget.style.transform = 'scale(1)';
              e.currentTarget.style.backgroundColor = 'var(--accent-primary)';
            }
          }}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
        </button>
      </form>
      
      {/* Keyframe animation for spinner */}
      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};

export default MessageInput;

import React, { useEffect, useRef } from 'react';
import { marked } from 'marked';

// Configure marked options
marked.setOptions({
  breaks: true,
  gfm: true
});

const ChatArea = ({ history, agentDetails, onApprove, onDeny, onToolClick }) => {
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [history]);

  const renderMessage = (msg, idx) => {
    const isUser = msg.type === 'user';
    const isSystem = msg.type === 'system';
    const isApproval = msg.type === 'approval_request';
    
    if (isApproval) {
      const isPending = !msg.decision || msg.decision === 'pending';
      const isApproved = msg.decision === 'approved';
      const isDenied = msg.decision === 'denied';
      
      return (
        <div key={idx} style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'flex-start',
          marginBottom: '20px',
          width: '100%',
          animation: 'fadeIn 0.3s ease-out'
        }}>
          <div style={{
            fontSize: '0.8rem',
            color: 'var(--text-muted)',
            marginBottom: '4px',
            marginLeft: '12px'
          }}>
            System Security Request
          </div>
          <div className="glass-panel" style={{
            width: '100%',
            maxWidth: '600px',
            padding: '16px 20px',
            borderRadius: '16px',
            backgroundColor: 'rgba(24, 24, 37, 0.95)',
            border: '1px solid var(--glass-border)',
            boxShadow: 'var(--glass-shadow)',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-warning)', fontWeight: '600' }}>
              <span style={{ fontSize: '1.1rem' }}>⚠️</span> {msg.title || "Terminal Command Authorization"}
            </div>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', margin: 0 }}>
              {msg.description ? "The agent is requesting permission for the following action:" : "The agent is requesting permission to execute the following shell command:"}
            </p>
            <div style={{
              fontFamily: msg.description ? 'inherit' : 'Courier New, Courier, monospace',
              backgroundColor: 'rgba(0, 0, 0, 0.4)',
              padding: '12px',
              borderRadius: '8px',
              color: 'var(--accent-primary)',
              fontSize: '0.9rem',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all',
              border: '1px solid rgba(255, 255, 255, 0.05)'
            }}>
              {msg.description || msg.content}
            </div>
            
            {isPending && (
              <div style={{ display: 'flex', gap: '12px', marginTop: '4px' }}>
                <button 
                  onClick={() => onApprove(msg.approval_id)}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '8px',
                    backgroundColor: 'var(--accent-success)',
                    color: '#11111b',
                    border: 'none',
                    fontWeight: '600',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    transition: 'all 0.2s ease',
                    boxShadow: '0 2px 8px rgba(166, 227, 161, 0.2)'
                  }}
                  onMouseOver={(e) => {
                    e.currentTarget.style.opacity = 0.85;
                    e.currentTarget.style.transform = 'translateY(-1px)';
                  }}
                  onMouseOut={(e) => {
                    e.currentTarget.style.opacity = 1;
                    e.currentTarget.style.transform = 'translateY(0)';
                  }}
                >
                  ✅ Approve
                </button>
                <button 
                  onClick={() => onDeny(msg.approval_id)}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '8px',
                    backgroundColor: 'var(--accent-danger)',
                    color: '#11111b',
                    border: 'none',
                    fontWeight: '600',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    transition: 'all 0.2s ease',
                    boxShadow: '0 2px 8px rgba(243, 139, 168, 0.2)'
                  }}
                  onMouseOver={(e) => {
                    e.currentTarget.style.opacity = 0.85;
                    e.currentTarget.style.transform = 'translateY(-1px)';
                  }}
                  onMouseOut={(e) => {
                    e.currentTarget.style.opacity = 1;
                    e.currentTarget.style.transform = 'translateY(0)';
                  }}
                >
                  ❌ Deny
                </button>
              </div>
            )}
            
            {isApproved && (
              <div style={{ 
                color: 'var(--accent-success)', 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px', 
                fontWeight: '600', 
                fontSize: '0.9rem',
                backgroundColor: 'rgba(166, 227, 161, 0.08)',
                padding: '6px 12px',
                borderRadius: '8px',
                width: 'fit-content'
              }}>
                <span>✓</span> Execution approved.
              </div>
            )}
            
            {isDenied && (
              <div style={{ 
                color: 'var(--accent-danger)', 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px', 
                fontWeight: '600', 
                fontSize: '0.9rem',
                backgroundColor: 'rgba(243, 139, 168, 0.08)',
                padding: '6px 12px',
                borderRadius: '8px',
                width: 'fit-content'
              }}>
                <span>✗</span> Execution denied.
              </div>
            )}
          </div>
        </div>
      );
    }

    if (isSystem) {
      if (msg.tool_call_id) {
        return (
          <div key={idx} style={{
            display: 'flex',
            justifyContent: 'center',
            margin: '16px 0'
          }}>
            <div 
              onClick={() => onToolClick && onToolClick(msg.tool_call_id)}
              style={{
                backgroundColor: 'var(--bg-surface)',
                color: 'var(--accent-primary)',
                padding: '6px 14px',
                borderRadius: '8px',
                fontSize: '0.85rem',
                border: '1px solid var(--glass-border)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                transition: 'all 0.2s'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--accent-primary)';
                e.currentTarget.style.transform = 'translateY(-1px)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--glass-border)';
                e.currentTarget.style.transform = 'translateY(0)';
              }}
            >
              <span>⚙️</span>
              <span style={{ fontWeight: '600' }}>{msg.content}</span>
            </div>
          </div>
        );
      }

      return (
        <div key={idx} style={{
          display: 'flex',
          justifyContent: 'center',
          margin: '16px 0'
        }}>
          <span style={{
            backgroundColor: 'var(--bg-surface)',
            color: 'var(--accent-warning)',
            padding: '4px 12px',
            borderRadius: '12px',
            fontSize: '0.8rem',
            fontStyle: 'italic',
            border: '1px solid var(--glass-border)'
          }}>
            [SYS] {msg.content}
          </span>
        </div>
      );
    }

    const agentDisplayName = !isUser && !isSystem && msg.agent && agentDetails && agentDetails[msg.agent]?.AI_NAME
      ? agentDetails[msg.agent].AI_NAME
      : msg.agent || 'Agent';

    return (
      <div key={idx} style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: isUser ? 'flex-end' : 'flex-start',
        marginBottom: '20px'
      }}>
        <div style={{
          fontSize: '0.8rem',
          color: 'var(--text-muted)',
          marginBottom: '4px',
          marginLeft: isUser ? '0' : '12px',
          marginRight: isUser ? '12px' : '0'
        }}>
          {isUser ? 'You' : agentDisplayName} {msg.channel && msg.channel !== 'Web' ? `[${msg.channel}]` : ''}
        </div>
        <div 
          className={`markdown-content ${isUser ? 'user-msg-container' : ''}`}
          style={{
            maxWidth: '80%',
            padding: '12px 16px',
            borderRadius: '16px',
            backgroundColor: isUser ? 'var(--accent-primary)' : 'var(--bg-surface)',
            color: isUser ? '#11111b' : 'var(--text-main)',
            borderBottomRightRadius: isUser ? '4px' : '16px',
            borderBottomLeftRadius: isUser ? '16px' : '4px',
            boxShadow: 'var(--glass-shadow)',
            border: isUser ? 'none' : '1px solid var(--glass-border)',
            lineHeight: '1.5'
          }}
          dangerouslySetInnerHTML={{ __html: marked.parse(msg.content) }}
        />
      </div>
    );
  };

  return (
    <div style={{
      flex: 1,
      overflowY: 'auto',
      padding: '24px',
      display: 'flex',
      flexDirection: 'column'
    }} ref={scrollRef}>
      {history.length === 0 ? (
        <div style={{
          margin: 'auto',
          color: 'var(--text-muted)',
          textAlign: 'center',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '12px'
        }}>
          <div style={{
            width: '64px',
            height: '64px',
            borderRadius: '50%',
            backgroundColor: 'var(--bg-surface)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '24px'
          }}>🤖</div>
          <p>No messages yet.</p>
          <p style={{ fontSize: '0.85rem' }}>Select an agent and start chatting!</p>
        </div>
      ) : (
        history.map((msg, idx) => renderMessage(msg, idx))
      )}
    </div>
  );
};

export default ChatArea;

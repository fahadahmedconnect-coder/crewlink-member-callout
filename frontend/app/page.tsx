'use client';

import { useState, useEffect, useCallback } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface User {
  id: string;
  email: string;
  role: string;
  local: { id: string; name: string } | null;
}

interface Announcement {
  id: string;
  title: string;
  body: string;
  push_preview: string;
  status: string;
  needs_ack: boolean;
  sent_at: string | null;
  created_at: string;
}

interface Stats {
  total: number;
  sent: number;
  read: number;
  acked: number;
}

export default function Home() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState('leader@local27.union');
  const [password, setPassword] = useState('password123');
  const [loginError, setLoginError] = useState('');

  // Announcement state
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState<Announcement | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  // Form state
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [pushPreview, setPushPreview] = useState('');
  const [needsAck, setNeedsAck] = useState(true);
  const [messy, setMessy] = useState('');
  const [aiLoading, setAiLoading] = useState(false);

  // Stats
  const [stats, setStats] = useState<Stats | null>(null);

  // Check auth on mount
  useEffect(() => {
    fetch(`${API_URL}/api/auth/me/`, { credentials: 'include' })
      .then(res => res.ok ? res.json() : null)
      .then(data => { setUser(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  // Load announcements
  useEffect(() => {
    if (user?.role === 'leadership') {
      fetch(`${API_URL}/api/leadership/announcements/`, { credentials: 'include' })
        .then(res => res.json())
        .then(setAnnouncements)
        .catch(console.error);
    }
  }, [user]);

  // Load selected announcement
  useEffect(() => {
    if (selectedId) {
      fetch(`${API_URL}/api/leadership/announcements/${selectedId}/`, { credentials: 'include' })
        .then(res => res.json())
        .then(data => {
          setAnnouncement(data);
          setTitle(data.title || '');
          setBody(data.body || '');
          setPushPreview(data.push_preview || '');
          setNeedsAck(data.needs_ack);
        })
        .catch(console.error);
    }
  }, [selectedId]);

  // Poll stats for sent/sending announcements
  useEffect(() => {
    if (!announcement || !['sent', 'sending'].includes(announcement.status)) {
      setStats(null);
      return;
    }
    const fetchStats = () => {
      fetch(`${API_URL}/api/leadership/announcements/${announcement.id}/stats/`, { credentials: 'include' })
        .then(res => res.json())
        .then(setStats)
        .catch(console.error);
    };
    fetchStats();
    const interval = setInterval(fetchStats, 2000);
    return () => clearInterval(interval);
  }, [announcement]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError('');
    try {
      const res = await fetch(`${API_URL}/api/auth/login/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, password }),
      });
      if (res.ok) {
        setUser(await res.json());
      } else {
        setLoginError('Invalid credentials');
      }
    } catch {
      setLoginError('Connection failed');
    }
  };

  const handleLogout = async () => {
    await fetch(`${API_URL}/api/auth/logout/`, { method: 'POST', credentials: 'include' });
    setUser(null);
    setAnnouncements([]);
    setAnnouncement(null);
    setSelectedId(null);
  };

  const handleCreate = () => {
    // Open empty form - no API call yet
    setSelectedId(null);
    setAnnouncement(null);
    setIsCreating(true);
    setTitle('');
    setBody('');
    setPushPreview('');
    setNeedsAck(true);
    setMessy('');
    setStats(null);
  };

  const handleSave = async () => {
    if (isCreating) {
      // Create new announcement
      const res = await fetch(`${API_URL}/api/leadership/announcements/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ title, body, push_preview: pushPreview, needs_ack: needsAck }),
      });
      if (res.ok) {
        const data = await res.json();
        setAnnouncements(prev => [data, ...prev]);
        setSelectedId(data.id);
        setIsCreating(false);
      }
    } else if (announcement) {
      // Update existing
      await fetch(`${API_URL}/api/leadership/announcements/${announcement.id}/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ title, body, push_preview: pushPreview, needs_ack: needsAck }),
      });
      setAnnouncements(prev => prev.map(a => a.id === announcement.id ? { ...a, title } : a));
    }
  };

  const handleAiCleanup = async () => {
    if (!messy.trim()) return;
    setAiLoading(true);
    try {
      // Use standalone AI cleanup endpoint (no announcement ID needed)
      const res = await fetch(`${API_URL}/api/ai/cleanup/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ messy_text: messy }),
      });
      if (res.ok) {
        const data = await res.json();
        setTitle(data.title);
        setBody(data.body);
        setPushPreview(data.push_preview);
        setMessy('');
      }
    } finally {
      setAiLoading(false);
    }
  };

  const handleApprove = async () => {
    if (!announcement) return;
    const res = await fetch(`${API_URL}/api/leadership/announcements/${announcement.id}/approve/`, {
      method: 'POST',
      credentials: 'include',
    });
    if (res.ok) {
      const data = await res.json();
      setAnnouncement(data);
      setAnnouncements(prev => prev.map(a => a.id === data.id ? data : a));
    }
  };

  const handleSend = async () => {
    if (!announcement) return;
    const res = await fetch(`${API_URL}/api/leadership/announcements/${announcement.id}/send/`, {
      method: 'POST',
      credentials: 'include',
    });
    if (res.ok) {
      const data = await res.json();
      setAnnouncement(data);
      setAnnouncements(prev => prev.map(a => a.id === data.id ? data : a));
    }
  };

  const clearForm = () => {
    setSelectedId(null);
    setAnnouncement(null);
    setIsCreating(false);
    setTitle('');
    setBody('');
    setPushPreview('');
    setNeedsAck(true);
    setMessy('');
    setStats(null);
  };

  const getStatusStyle = (status: string) => {
    switch (status) {
      case 'sent': return { background: 'var(--success-bg)', color: 'var(--success)', border: '1px solid var(--success)' };
      case 'sending': return { background: 'var(--warning-bg)', color: 'var(--warning)', border: '1px solid var(--warning)' };
      case 'approved': return { background: 'var(--accent-light)', color: 'var(--accent)', border: '1px solid var(--accent)' };
      default: return { background: 'var(--bg-warm)', color: 'var(--text-muted)', border: '1px solid var(--border-light)' };
    }
  };

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ fontFamily: 'var(--font-display)', fontSize: '1.5rem', color: 'var(--text-muted)', letterSpacing: '0.1em' }}>
          LOADING...
        </div>
      </div>
    );
  }

  // LOGIN SCREEN
  if (!user) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(180deg, var(--bg-cream) 0%, var(--bg-warm) 100%)',
        padding: '2rem',
      }}>
        <div className="animate-in" style={{
          width: '100%',
          maxWidth: '400px',
          background: 'var(--bg-paper)',
          border: '1px solid var(--border-light)',
          boxShadow: '0 4px 24px rgba(26, 39, 68, 0.08)',
        }}>
          {/* Header bar */}
          <div style={{
            background: 'var(--navy)',
            padding: '1.5rem 2rem',
            borderBottom: '4px solid var(--accent)',
          }}>
            <h1 style={{
              fontFamily: 'var(--font-display)',
              fontSize: '2.5rem',
              color: 'white',
              letterSpacing: '0.08em',
              lineHeight: 1,
            }}>CREWLINK</h1>
            <p style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.7rem',
              color: 'rgba(255,255,255,0.6)',
              letterSpacing: '0.15em',
              marginTop: '0.5rem',
            }}>MEMBER CALLOUT SYSTEM</p>
          </div>

          <form onSubmit={handleLogin} style={{ padding: '2rem' }}>
            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{
                display: 'block',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.65rem',
                fontWeight: 600,
                letterSpacing: '0.15em',
                color: 'var(--text-muted)',
                marginBottom: '0.5rem',
                textTransform: 'uppercase',
              }}>Email</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.875rem 1rem',
                  border: '2px solid var(--border-light)',
                  background: 'var(--bg-cream)',
                  fontFamily: 'var(--font-body)',
                  fontSize: '1rem',
                  color: 'var(--text-body)',
                  transition: 'border-color 0.2s',
                }}
                onFocus={e => e.target.style.borderColor = 'var(--navy)'}
                onBlur={e => e.target.style.borderColor = 'var(--border-light)'}
              />
            </div>

            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{
                display: 'block',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.65rem',
                fontWeight: 600,
                letterSpacing: '0.15em',
                color: 'var(--text-muted)',
                marginBottom: '0.5rem',
                textTransform: 'uppercase',
              }}>Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.875rem 1rem',
                  border: '2px solid var(--border-light)',
                  background: 'var(--bg-cream)',
                  fontFamily: 'var(--font-body)',
                  fontSize: '1rem',
                  color: 'var(--text-body)',
                  transition: 'border-color 0.2s',
                }}
                onFocus={e => e.target.style.borderColor = 'var(--navy)'}
                onBlur={e => e.target.style.borderColor = 'var(--border-light)'}
              />
            </div>

            {loginError && (
              <div style={{
                padding: '0.75rem 1rem',
                background: 'var(--error-bg)',
                color: 'var(--error)',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.8rem',
                marginBottom: '1.5rem',
                border: '1px solid var(--error)',
              }}>{loginError}</div>
            )}

            <button type="submit" style={{
              width: '100%',
              padding: '1rem',
              background: 'var(--accent)',
              color: 'white',
              border: 'none',
              fontFamily: 'var(--font-display)',
              fontSize: '1.1rem',
              letterSpacing: '0.1em',
              cursor: 'pointer',
              transition: 'background 0.2s',
            }}
            onMouseOver={e => (e.target as HTMLElement).style.background = 'var(--accent-hover)'}
            onMouseOut={e => (e.target as HTMLElement).style.background = 'var(--accent)'}
            >SIGN IN</button>

            <p style={{
              marginTop: '1.5rem',
              textAlign: 'center',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.7rem',
              color: 'var(--text-faint)',
            }}>
              Test: leader@local27.union / password123
            </p>
          </form>
        </div>
      </div>
    );
  }

  // DASHBOARD
  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-cream)' }}>
      {/* Header */}
      <header style={{
        background: 'var(--navy)',
        borderBottom: '4px solid var(--accent)',
        padding: '0 2rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: '64px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
          <h1 style={{
            fontFamily: 'var(--font-display)',
            fontSize: '1.75rem',
            color: 'white',
            letterSpacing: '0.08em',
          }}>CREWLINK</h1>
          {user.local && (
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.7rem',
              color: 'var(--accent-light)',
              letterSpacing: '0.1em',
              padding: '0.25rem 0.75rem',
              border: '1px solid var(--accent)',
              background: 'rgba(194, 65, 12, 0.1)',
            }}>{user.local.name.toUpperCase()}</span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.75rem',
            color: 'rgba(255,255,255,0.7)',
          }}>{user.email}</span>
          <button onClick={handleLogout} style={{
            padding: '0.5rem 1rem',
            background: 'transparent',
            border: '1px solid rgba(255,255,255,0.3)',
            color: 'white',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.7rem',
            letterSpacing: '0.1em',
            cursor: 'pointer',
            transition: 'all 0.2s',
          }}
          onMouseOver={e => { (e.target as HTMLElement).style.background = 'rgba(255,255,255,0.1)'; }}
          onMouseOut={e => { (e.target as HTMLElement).style.background = 'transparent'; }}
          >LOGOUT</button>
        </div>
      </header>

      {/* Main content */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '280px 1fr',
        minHeight: 'calc(100vh - 64px)',
      }}>
        {/* Sidebar */}
        <aside style={{
          background: 'var(--bg-paper)',
          borderRight: '1px solid var(--border-light)',
          padding: '1.5rem',
          display: 'flex',
          flexDirection: 'column',
        }}>
          <button onClick={handleCreate} style={{
            width: '100%',
            padding: '0.875rem',
            background: 'var(--accent)',
            color: 'white',
            border: 'none',
            fontFamily: 'var(--font-display)',
            fontSize: '1rem',
            letterSpacing: '0.1em',
            cursor: 'pointer',
            marginBottom: '1.5rem',
            transition: 'background 0.2s',
          }}
          onMouseOver={e => (e.target as HTMLElement).style.background = 'var(--accent-hover)'}
          onMouseOut={e => (e.target as HTMLElement).style.background = 'var(--accent)'}
          >+ NEW ANNOUNCEMENT</button>

          <h3 style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.65rem',
            letterSpacing: '0.2em',
            color: 'var(--text-muted)',
            marginBottom: '1rem',
            paddingBottom: '0.5rem',
            borderBottom: '1px solid var(--border-light)',
          }}>ANNOUNCEMENTS</h3>

          <div style={{ flex: 1, overflow: 'auto' }}>
            {announcements.map(a => (
              <div
                key={a.id}
                onClick={() => setSelectedId(a.id)}
                style={{
                  padding: '0.875rem',
                  marginBottom: '0.5rem',
                  background: selectedId === a.id ? 'var(--bg-highlight)' : 'var(--bg-cream)',
                  border: selectedId === a.id ? '1px solid var(--accent)' : '1px solid transparent',
                  cursor: 'pointer',
                  transition: 'all 0.15s',
                }}
              >
                <div style={{
                  fontFamily: 'var(--font-body)',
                  fontWeight: 600,
                  fontSize: '0.9rem',
                  color: 'var(--text-headline)',
                  marginBottom: '0.5rem',
                  lineHeight: 1.3,
                }}>{a.title || 'Untitled'}</div>
                <span style={{
                  ...getStatusStyle(a.status),
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.6rem',
                  letterSpacing: '0.1em',
                  padding: '0.2rem 0.5rem',
                  textTransform: 'uppercase',
                  display: 'inline-block',
                }}>{a.status}</span>
              </div>
            ))}
            {announcements.length === 0 && (
              <p style={{
                fontFamily: 'var(--font-body)',
                fontStyle: 'italic',
                color: 'var(--text-faint)',
                fontSize: '0.9rem',
              }}>No announcements yet</p>
            )}
          </div>
        </aside>

        {/* Main panel */}
        <main style={{ padding: '2rem 3rem', overflow: 'auto' }}>
          {!announcement && !isCreating ? (
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              color: 'var(--text-muted)',
            }}>
              <div style={{
                width: '80px',
                height: '80px',
                border: '3px dashed var(--border-medium)',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: '1.5rem',
              }}>
                <span style={{ fontSize: '2rem' }}>+</span>
              </div>
              <p style={{ fontFamily: 'var(--font-body)', fontSize: '1.1rem' }}>
                Select or create an announcement
              </p>
            </div>
          ) : (
            <div className="animate-in">
              {/* Status bar */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '2rem',
                paddingBottom: '1rem',
                borderBottom: '2px solid var(--border-light)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                  {isCreating ? (
                    <>
                      <span style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.7rem',
                        fontWeight: 600,
                        letterSpacing: '0.1em',
                        padding: '0.4rem 0.75rem',
                        textTransform: 'uppercase',
                        background: 'var(--accent-light)',
                        color: 'var(--accent)',
                        border: '1px solid var(--accent)',
                      }}>NEW</span>
                      <span style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.7rem',
                        color: 'var(--text-faint)',
                      }}>Create new announcement</span>
                    </>
                  ) : announcement && (
                    <>
                      <span style={{
                        ...getStatusStyle(announcement.status),
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.7rem',
                        fontWeight: 600,
                        letterSpacing: '0.1em',
                        padding: '0.4rem 0.75rem',
                        textTransform: 'uppercase',
                      }}>{announcement.status}</span>
                      {announcement.status === 'draft' && (
                        <span style={{
                          fontFamily: 'var(--font-mono)',
                          fontSize: '0.7rem',
                          color: 'var(--text-faint)',
                        }}>Editing...</span>
                      )}
                    </>
                  )}
                </div>
                <button onClick={clearForm} style={{
                  padding: '0.5rem 1rem',
                  background: 'transparent',
                  border: '1px solid var(--border-medium)',
                  color: 'var(--text-muted)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.7rem',
                  letterSpacing: '0.05em',
                  cursor: 'pointer',
                }}>CLOSE</button>
              </div>

              {/* AI Cleanup - available for new and draft announcements */}
              {(isCreating || announcement?.status === 'draft') && (
                <div style={{
                  background: 'var(--bg-warm)',
                  border: '1px solid var(--border-light)',
                  padding: '1.5rem',
                  marginBottom: '2rem',
                }}>
                  <h4 style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.7rem',
                    letterSpacing: '0.15em',
                    color: 'var(--text-muted)',
                    marginBottom: '1rem',
                  }}>AI CLEANUP</h4>
                  <textarea
                    value={messy}
                    onChange={e => setMessy(e.target.value)}
                    placeholder="Paste messy notes, emails, or rough text here..."
                    style={{
                      width: '100%',
                      minHeight: '100px',
                      padding: '1rem',
                      border: '1px solid var(--border-light)',
                      background: 'var(--bg-paper)',
                      fontFamily: 'var(--font-body)',
                      fontSize: '0.95rem',
                      resize: 'vertical',
                      color: 'var(--text-body)',
                    }}
                  />
                  <button
                    onClick={handleAiCleanup}
                    disabled={aiLoading || !messy.trim()}
                    style={{
                      marginTop: '1rem',
                      padding: '0.75rem 1.5rem',
                      background: aiLoading ? 'var(--text-faint)' : 'var(--navy)',
                      color: 'white',
                      border: 'none',
                      fontFamily: 'var(--font-mono)',
                      fontSize: '0.75rem',
                      letterSpacing: '0.1em',
                      cursor: aiLoading ? 'wait' : 'pointer',
                      opacity: !messy.trim() ? 0.5 : 1,
                    }}
                  >{aiLoading ? 'PROCESSING...' : 'CLEAN UP WITH AI'}</button>
                </div>
              )}

              {/* Form */}
              {(() => {
                const isEditable = isCreating || announcement?.status === 'draft';
                return (
                  <>
                    <div style={{ marginBottom: '2rem' }}>
                      <label style={{
                        display: 'block',
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.65rem',
                        fontWeight: 600,
                        letterSpacing: '0.15em',
                        color: 'var(--text-muted)',
                        marginBottom: '0.5rem',
                        textTransform: 'uppercase',
                      }}>Title</label>
                      <input
                        value={title}
                        onChange={e => setTitle(e.target.value)}
                        disabled={!isEditable}
                        placeholder="Enter announcement title..."
                        style={{
                          width: '100%',
                          padding: '1rem',
                          border: '2px solid var(--border-light)',
                          background: isEditable ? 'var(--bg-paper)' : 'var(--bg-warm)',
                          fontFamily: 'var(--font-body)',
                          fontSize: '1.25rem',
                          fontWeight: 600,
                          color: 'var(--text-headline)',
                        }}
                      />
                    </div>

                    <div style={{ marginBottom: '2rem' }}>
                      <label style={{
                        display: 'block',
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.65rem',
                        fontWeight: 600,
                        letterSpacing: '0.15em',
                        color: 'var(--text-muted)',
                        marginBottom: '0.5rem',
                        textTransform: 'uppercase',
                      }}>Body</label>
                      <textarea
                        value={body}
                        onChange={e => setBody(e.target.value)}
                        disabled={!isEditable}
                        placeholder="Enter announcement body..."
                        style={{
                          width: '100%',
                          minHeight: '180px',
                          padding: '1rem',
                          border: '2px solid var(--border-light)',
                          background: isEditable ? 'var(--bg-paper)' : 'var(--bg-warm)',
                          fontFamily: 'var(--font-body)',
                          fontSize: '1rem',
                          lineHeight: 1.7,
                          resize: 'vertical',
                          color: 'var(--text-body)',
                        }}
                      />
                    </div>

                    <div style={{ marginBottom: '2rem' }}>
                      <label style={{
                        display: 'block',
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.65rem',
                        fontWeight: 600,
                        letterSpacing: '0.15em',
                        color: 'var(--text-muted)',
                        marginBottom: '0.5rem',
                        textTransform: 'uppercase',
                      }}>Push Preview <span style={{ opacity: 0.5 }}>(120 chars max)</span></label>
                      <input
                        value={pushPreview}
                        onChange={e => setPushPreview(e.target.value.slice(0, 120))}
                        disabled={!isEditable}
                        placeholder="Short preview for push notification..."
                        style={{
                          width: '100%',
                          padding: '1rem',
                          border: '2px solid var(--border-light)',
                          background: isEditable ? 'var(--bg-paper)' : 'var(--bg-warm)',
                          fontFamily: 'var(--font-body)',
                          fontSize: '0.95rem',
                          color: 'var(--text-body)',
                        }}
                      />
                      <div style={{
                        textAlign: 'right',
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.7rem',
                        color: pushPreview.length > 100 ? 'var(--warning)' : 'var(--text-faint)',
                        marginTop: '0.25rem',
                      }}>{pushPreview.length}/120</div>
                    </div>

                    <div style={{ marginBottom: '2rem' }}>
                      <label style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.75rem',
                        cursor: isEditable ? 'pointer' : 'default',
                      }}>
                        <input
                          type="checkbox"
                          checked={needsAck}
                          onChange={e => setNeedsAck(e.target.checked)}
                          disabled={!isEditable}
                          style={{
                            width: '1.25rem',
                            height: '1.25rem',
                            accentColor: 'var(--accent)',
                          }}
                        />
                        <span style={{
                          fontFamily: 'var(--font-body)',
                          fontSize: '0.95rem',
                          color: 'var(--text-body)',
                        }}>Require acknowledgment from members</span>
                      </label>
                    </div>
                  </>
                );
              })()}

              {/* Action buttons */}
              {/* Action buttons */}
              <div style={{
                display: 'flex',
                gap: '1rem',
                paddingTop: '1.5rem',
                borderTop: '1px solid var(--border-light)',
              }}>
                {isCreating && (
                  <button onClick={handleSave} style={{
                    padding: '0.875rem 1.5rem',
                    background: 'var(--accent)',
                    color: 'white',
                    border: 'none',
                    fontFamily: 'var(--font-display)',
                    fontSize: '1rem',
                    letterSpacing: '0.08em',
                    cursor: 'pointer',
                  }}>CREATE ANNOUNCEMENT</button>
                )}
                {!isCreating && announcement?.status === 'draft' && (
                  <>
                    <button onClick={handleSave} style={{
                      padding: '0.875rem 1.5rem',
                      background: 'var(--navy)',
                      color: 'white',
                      border: 'none',
                      fontFamily: 'var(--font-display)',
                      fontSize: '1rem',
                      letterSpacing: '0.08em',
                      cursor: 'pointer',
                    }}>SAVE DRAFT</button>
                    <button onClick={handleApprove} style={{
                      padding: '0.875rem 1.5rem',
                      background: 'var(--accent)',
                      color: 'white',
                      border: 'none',
                      fontFamily: 'var(--font-display)',
                      fontSize: '1rem',
                      letterSpacing: '0.08em',
                      cursor: 'pointer',
                    }}>APPROVE</button>
                  </>
                )}
                {!isCreating && announcement?.status === 'approved' && (
                  <button onClick={handleSend} style={{
                    padding: '0.875rem 2rem',
                    background: 'var(--success)',
                    color: 'white',
                    border: 'none',
                    fontFamily: 'var(--font-display)',
                    fontSize: '1rem',
                    letterSpacing: '0.08em',
                    cursor: 'pointer',
                  }}>SEND TO ALL MEMBERS</button>
                )}
              </div>

              {/* Stats for sent/sending */}
              {stats && announcement && ['sent', 'sending'].includes(announcement.status) && (
                <div style={{
                  marginTop: '3rem',
                  padding: '2rem',
                  background: 'var(--bg-paper)',
                  border: '2px solid var(--border-light)',
                }}>
                  <h3 style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: '1.25rem',
                    letterSpacing: '0.1em',
                    color: 'var(--text-headline)',
                    marginBottom: '1.5rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.75rem',
                  }}>
                    DELIVERY STATS
                    {announcement.status === 'sending' && (
                      <span style={{
                        width: '8px',
                        height: '8px',
                        borderRadius: '50%',
                        background: 'var(--warning)',
                        animation: 'pulse-soft 1s infinite',
                      }} />
                    )}
                  </h3>
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(3, 1fr)',
                    gap: '1.5rem',
                  }}>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '2.5rem',
                        fontWeight: 600,
                        color: 'var(--navy)',
                      }}>{stats.sent}</div>
                      <div style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.65rem',
                        letterSpacing: '0.15em',
                        color: 'var(--text-muted)',
                        marginTop: '0.25rem',
                      }}>DELIVERED</div>
                      <div style={{
                        height: '4px',
                        background: 'var(--bg-warm)',
                        marginTop: '0.75rem',
                        overflow: 'hidden',
                      }}>
                        <div style={{
                          height: '100%',
                          width: `${stats.total ? (stats.sent / stats.total) * 100 : 0}%`,
                          background: 'var(--navy)',
                          transition: 'width 0.5s ease-out',
                        }} />
                      </div>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '2.5rem',
                        fontWeight: 600,
                        color: 'var(--accent)',
                      }}>{stats.read}</div>
                      <div style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.65rem',
                        letterSpacing: '0.15em',
                        color: 'var(--text-muted)',
                        marginTop: '0.25rem',
                      }}>READ</div>
                      <div style={{
                        height: '4px',
                        background: 'var(--bg-warm)',
                        marginTop: '0.75rem',
                        overflow: 'hidden',
                      }}>
                        <div style={{
                          height: '100%',
                          width: `${stats.sent ? (stats.read / stats.sent) * 100 : 0}%`,
                          background: 'var(--accent)',
                          transition: 'width 0.5s ease-out',
                        }} />
                      </div>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '2.5rem',
                        fontWeight: 600,
                        color: 'var(--success)',
                      }}>{stats.acked}</div>
                      <div style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.65rem',
                        letterSpacing: '0.15em',
                        color: 'var(--text-muted)',
                        marginTop: '0.25rem',
                      }}>ACKNOWLEDGED</div>
                      <div style={{
                        height: '4px',
                        background: 'var(--bg-warm)',
                        marginTop: '0.75rem',
                        overflow: 'hidden',
                      }}>
                        <div style={{
                          height: '100%',
                          width: `${stats.sent ? (stats.acked / stats.sent) * 100 : 0}%`,
                          background: 'var(--success)',
                          transition: 'width 0.5s ease-out',
                        }} />
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

function usage() {
  console.error(`Usage:
  /Users/robin/.nvm/versions/node/v24.14.0/bin/node scripts/clawith_ws_roundtrip.js \
    --token-file runtime/clawith_bearer_token.txt \
    --agent-name vibecosystem-adapter \
    --message "Give me a 2-bullet summary of this repo." \
    --base-url http://localhost:3008

Options:
  --base-url URL           Clawith base URL (default: http://localhost:3008)
  --token TOKEN            Bearer token for Clawith API/websocket auth
  --token-file PATH        Read bearer token from file
  --agent-id UUID          Target agent id
  --agent-name NAME        Target agent name (default: vibecosystem-adapter)
  --message TEXT           Message to send
  --message-file PATH      Read message text from file
  --session-title TEXT     New session title (default: clawith roundtrip <timestamp>)
  --timeout-sec N          Wait timeout in seconds (default: 180)
  --artifacts-dir PATH     Artifact root (default: artifacts/clawith-roundtrip)
`);
}

function timestamp() {
  return new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
}

function parseArgs(argv) {
  const args = {
    baseUrl: 'http://localhost:3008',
    agentName: 'vibecosystem-adapter',
    timeoutSec: 180,
    artifactsDir: 'artifacts/clawith-roundtrip',
  };
  for (let i = 0; i < argv.length; i += 1) {
    const key = argv[i];
    const next = argv[i + 1];
    if (!key.startsWith('--')) {
      throw new Error(`Unexpected argument: ${key}`);
    }
    switch (key) {
      case '--base-url':
        args.baseUrl = next; i += 1; break;
      case '--token':
        args.token = next; i += 1; break;
      case '--token-file':
        args.tokenFile = next; i += 1; break;
      case '--agent-id':
        args.agentId = next; i += 1; break;
      case '--agent-name':
        args.agentName = next; i += 1; break;
      case '--message':
        args.message = next; i += 1; break;
      case '--message-file':
        args.messageFile = next; i += 1; break;
      case '--session-title':
        args.sessionTitle = next; i += 1; break;
      case '--timeout-sec':
        args.timeoutSec = Number(next); i += 1; break;
      case '--artifacts-dir':
        args.artifactsDir = next; i += 1; break;
      case '--help':
        usage();
        process.exit(0);
      default:
        throw new Error(`Unknown option: ${key}`);
    }
  }
  return args;
}

function ensureParent(filePath) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
}

function writeJson(filePath, value) {
  ensureParent(filePath);
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

function writeText(filePath, value) {
  ensureParent(filePath);
  fs.writeFileSync(filePath, value, 'utf8');
}

async function httpJson(method, url, token, body) {
  const headers = {};
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const options = { method, headers };
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(body);
  }
  const resp = await fetch(url, options);
  const raw = await resp.text();
  let json = null;
  try {
    json = raw ? JSON.parse(raw) : null;
  } catch {
    json = null;
  }
  if (!resp.ok) {
    throw new Error(`${method} ${url} -> HTTP ${resp.status}: ${raw}`);
  }
  return json;
}

async function resolveAgent(baseUrl, token, agentId, agentName) {
  const agents = await httpJson('GET', `${baseUrl}/api/agents/`, token);
  if (!Array.isArray(agents)) {
    throw new Error(`Expected array from /api/agents/, got ${typeof agents}`);
  }
  if (agentId) {
    const hit = agents.find((agent) => String(agent.id) === String(agentId));
    if (!hit) {
      throw new Error(`Agent id not found: ${agentId}`);
    }
    return hit;
  }

  const exact = agents.filter((agent) => agent.name === agentName);
  if (exact.length === 1) return exact[0];
  if (exact.length > 1) {
    throw new Error(`Multiple exact agent-name matches for ${agentName}`);
  }

  const ciExact = agents.filter((agent) => String(agent.name || '').toLowerCase() === String(agentName || '').toLowerCase());
  if (ciExact.length === 1) return ciExact[0];
  if (ciExact.length > 1) {
    throw new Error(`Multiple case-insensitive agent-name matches for ${agentName}`);
  }

  const partial = agents.filter((agent) => String(agent.name || '').toLowerCase().includes(String(agentName || '').toLowerCase()));
  if (partial.length === 1) return partial[0];
  if (partial.length > 1) {
    throw new Error(`Multiple partial agent-name matches for ${agentName}: ${partial.map((a) => a.name).join(', ')}`);
  }

  throw new Error(`No agent found for name: ${agentName}`);
}

function redactUrlForArtifact(wsUrl) {
  const url = new URL(wsUrl);
  if (url.searchParams.has('token')) {
    url.searchParams.set('token', 'REDACTED');
  }
  return url.toString();
}

async function waitForRoundTrip(wsUrl, prompt, timeoutMs, receiptDir) {
  const events = [];
  const ws = new WebSocket(wsUrl);
  const forwardPlaceholder = 'Message forwarded to OpenClaw agent. Waiting for response...';

  const pushEvent = (kind, payload) => {
    events.push({
      at: new Date().toISOString(),
      kind,
      payload,
    });
  };

  return await new Promise((resolve, reject) => {
    let settled = false;
    let promptSent = false;
    let placeholderSeen = false;

    const finish = (err, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      try {
        if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
          ws.close();
        }
      } catch {}
      writeJson(path.join(receiptDir, 'ws_events.json'), events);
      if (err) {
        reject(err);
      } else {
        resolve({ ...value, events, placeholderSeen });
      }
    };

    const timer = setTimeout(() => {
      finish(new Error(`Timed out after ${timeoutMs}ms waiting for final assistant reply`));
    }, timeoutMs);

    ws.addEventListener('open', () => {
      pushEvent('open', { ok: true });
      ws.send(JSON.stringify({ content: prompt }));
      promptSent = true;
      pushEvent('send', { content: prompt });
    });

    ws.addEventListener('message', (event) => {
      let data = event.data;
      try {
        data = JSON.parse(event.data);
      } catch {}
      pushEvent('message', data);

      if (!promptSent) return;
      if (!data || typeof data !== 'object') return;
      if (data.type !== 'done' || data.role !== 'assistant') return;

      const content = String(data.content || '');
      if (content === forwardPlaceholder) {
        placeholderSeen = true;
        return;
      }
      finish(null, { finalReply: content });
    });

    ws.addEventListener('error', (event) => {
      pushEvent('error', { message: event.message || 'websocket error' });
    });

    ws.addEventListener('close', (event) => {
      pushEvent('close', { code: event.code, reason: event.reason || '' });
      if (!settled) {
        finish(new Error(`WebSocket closed before final reply (code=${event.code}, reason=${event.reason || ''})`));
      }
    });
  });
}

async function main() {
  let args;
  try {
    args = parseArgs(process.argv.slice(2));
  } catch (err) {
    usage();
    throw err;
  }

  const token = args.token || (args.tokenFile ? fs.readFileSync(args.tokenFile, 'utf8').trim() : '');
  const message = args.message || (args.messageFile ? fs.readFileSync(args.messageFile, 'utf8') : '');
  if (!token) throw new Error('Missing --token or --token-file');
  if (!message || !message.trim()) throw new Error('Missing --message or --message-file');
  if (!Number.isFinite(args.timeoutSec) || args.timeoutSec <= 0) {
    throw new Error(`Invalid --timeout-sec: ${args.timeoutSec}`);
  }

  const runDir = path.resolve(args.artifactsDir, timestamp());
  fs.mkdirSync(runDir, { recursive: true });

  const agent = await resolveAgent(args.baseUrl, token, args.agentId, args.agentName);
  writeJson(path.join(runDir, 'agent.json'), {
    id: agent.id,
    name: agent.name,
    agent_type: agent.agent_type,
    role_description: agent.role_description,
  });

  const sessionTitle = args.sessionTitle || `clawith roundtrip ${timestamp()}`;
  const session = await httpJson(
    'POST',
    `${args.baseUrl}/api/agents/${agent.id}/sessions`,
    token,
    { title: sessionTitle },
  );
  writeJson(path.join(runDir, 'session.json'), session);
  writeText(path.join(runDir, 'prompt.txt'), message.endsWith('\n') ? message : `${message}\n`);

  const wsBase = args.baseUrl.replace(/^http:/i, 'ws:').replace(/^https:/i, 'wss:');
  const wsUrl = `${wsBase}/ws/chat/${agent.id}?token=${encodeURIComponent(token)}&session_id=${encodeURIComponent(session.id)}`;
  writeJson(path.join(runDir, 'transport.json'), {
    base_url: args.baseUrl,
    websocket_url: redactUrlForArtifact(wsUrl),
    timeout_sec: args.timeoutSec,
  });

  const wsResult = await waitForRoundTrip(wsUrl, message, args.timeoutSec * 1000, runDir);
  writeJson(path.join(runDir, 'ws_summary.json'), {
    placeholder_seen: wsResult.placeholderSeen,
    final_reply: wsResult.finalReply,
  });
  writeText(path.join(runDir, 'final_reply.txt'), wsResult.finalReply.endsWith('\n') ? wsResult.finalReply : `${wsResult.finalReply}\n`);

  const sessionMessages = await httpJson(
    'GET',
    `${args.baseUrl}/api/agents/${agent.id}/sessions/${session.id}/messages`,
    token,
  );
  writeJson(path.join(runDir, 'session_messages.json'), sessionMessages);

  const assistantMessages = Array.isArray(sessionMessages)
    ? sessionMessages.filter((msg) => msg && msg.role === 'assistant').map((msg) => String(msg.content || ''))
    : [];
  const responseInSession = assistantMessages.includes(wsResult.finalReply);

  const summary = {
    artifact_dir: runDir,
    agent_id: String(agent.id),
    agent_name: String(agent.name),
    session_id: String(session.id),
    placeholder_seen: wsResult.placeholderSeen,
    final_reply: wsResult.finalReply,
    response_in_session: responseInSession,
  };
  writeJson(path.join(runDir, 'summary.json'), summary);

  if (!responseInSession) {
    throw new Error(`Final reply did not appear in session message fetch. Artifacts: ${runDir}`);
  }

  console.log(JSON.stringify(summary, null, 2));
}

main().catch((err) => {
  console.error(err && err.stack ? err.stack : String(err));
  process.exit(1);
});

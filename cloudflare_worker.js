/**
 * Cloudflare Worker for AnimeKhor Telegram Bot
 * ============================================
 * Provides instant (< 1 second) responses for Telegram commands:
 * - /last : Instant latest episode with 16:9 thumbnail and direct link
 * - /link <page_url> : Instant webpage to video link conversion
 * - /dl <link> : Immediate loading reply, triggers GitHub Actions for Best HD cloud rendering
 *
 * Environment Variables required in Cloudflare Worker:
 * - TELEGRAM_BOT_TOKEN : Telegram bot token from @BotFather
 * - TELEGRAM_CHAT_ID   : (Optional) Restrict access to your numeric Chat ID
 * - GITHUB_TOKEN      : GitHub Personal Access Token (PAT with 'repo' scope)
 * - GITHUB_REPO       : "codekere/animekhor-notifier"
 */

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("OK", { status: 200 });
    }

    try {
      const update = await request.json();
      await handleTelegramUpdate(update, env);
    } catch (err) {
      console.error("Worker error:", err);
    }

    return new Response("OK", { status: 200 });
  }
};

async function handleTelegramUpdate(update, env) {
  const botToken = env.TELEGRAM_BOT_TOKEN;
  const allowedChatId = env.TELEGRAM_CHAT_ID;
  const githubToken = env.GITHUB_TOKEN;
  const githubRepo = env.GITHUB_REPO || "codekere/animekhor-notifier";

  // 1. Handle Callback Query (Dismiss button)
  if (update.callback_query) {
    const cb = update.callback_query;
    if (cb.data === "dismiss") {
      await deleteTelegramMessage(botToken, cb.message.chat.id, cb.message.message_id);
      await answerCallbackQuery(botToken, cb.id, "Dismissed");
    }
    return;
  }

  const msg = update.message;
  if (!msg || !msg.text) return;

  const chatId = String(msg.chat.id);
  const text = msg.text.trim();
  const userMsgId = msg.message_id;

  // Security check: restrict to your Chat ID if configured
  if (allowedChatId && chatId !== String(allowedChatId)) {
    return;
  }

  // 2. Command: /start or /help
  if (text.startsWith("/start") || text.startsWith("/help")) {
    const welcome =
      `👋 <b>AnimeKhor Notifier & Cloud Processor</b>\n\n` +
      `<b>Features:</b>\n` +
      `• Instant sub-second responses via Cloudflare Workers\n` +
      `• 16:9 Full HD Thumbnails for YouTube\n\n` +
      `<b>Commands:</b>\n` +
      `• /last - Check latest episode from AnimeKhor\n` +
      `• /link &lt;page-url&gt; - Convert webpage URL to direct video link\n` +
      `• /dl - Download latest episode in Best HD (Watermark removed)\n` +
      `• /dl &lt;link&gt; - Download specific video in Best HD`;
    await sendTelegram(botToken, chatId, welcome);
    return;
  }

  // 3. Command: /last (Fetch latest episode instantly)
  if (text.startsWith("/last")) {
    const latest = await getLatestRssItem();
    if (!latest) {
      await sendTelegram(botToken, chatId, "❌ Failed to fetch latest episode.");
      return;
    }

    const videoUrl = await extractVideoLink(latest.link);
    const thumbUrl = await getDailymotionThumbnail(videoUrl);
    const cleanTitle = cleanTitleForDisplay(latest.title);

    const caption =
      `🎬 <b>Latest Episode:</b>\n\n` +
      `📌 <b>Title:</b>\n<code>${cleanTitle}</code>\n\n` +
      `🔗 <b>Direct Link:</b>\n<code>${videoUrl}</code>`;

    if (thumbUrl) {
      await sendTelegramPhoto(botToken, chatId, thumbUrl, caption);
    } else {
      await sendTelegram(botToken, chatId, caption);
    }
    return;
  }

  // 4. Command: /link <page_url> (Convert AnimeKhor page instantly)
  if (text.startsWith("/link")) {
    const parts = text.split(/\s+/);
    let targetPage = parts[1] || "";

    if (!targetPage && msg.reply_to_message && msg.reply_to_message.text) {
      const match = msg.reply_to_message.text.match(/https?:\/\/[^\s<>"]+/);
      if (match) targetPage = match[0];
    }

    // Default to latest episode if no link provided
    if (!targetPage) {
      const latest = await getLatestRssItem();
      if (latest) targetPage = latest.link;
    }

    if (!targetPage) {
      await sendTelegram(botToken, chatId, "❌ <b>Usage:</b> <code>/link &lt;animekhor-page-url&gt;</code>");
      return;
    }

    const videoUrl = await extractVideoLink(targetPage);
    const thumbUrl = await getDailymotionThumbnail(videoUrl);
    const pageSlug = targetPage.replace(/\/+$/, "").split("/").pop().replace(/-/g, " ");

    const caption =
      `🎬 <b>Direct Video Link Ready!</b>\n\n` +
      `📌 <b>Page:</b>\n<code>${pageSlug}</code>\n\n` +
      `🔗 <b>Direct Link:</b>\n<code>${videoUrl}</code>`;

    if (thumbUrl) {
      await sendTelegramPhoto(botToken, chatId, thumbUrl, caption);
    } else {
      await sendTelegram(botToken, chatId, caption);
    }
    return;
  }

  // 5. Command: /dl (Trigger cloud watermark removal)
  if (text.startsWith("/dl")) {
    await deleteTelegramMessage(botToken, chatId, userMsgId);

    const parts = text.split(/\s+/);
    let targetLink = parts[1] || "";

    if (!targetLink && msg.reply_to_message && msg.reply_to_message.text) {
      const match = msg.reply_to_message.text.match(/https?:\/\/[^\s<>"]+/);
      if (match) targetLink = match[0];
    }

    if (!targetLink) {
      const latest = await getLatestRssItem();
      if (latest) targetLink = latest.link;
    }

    if (!targetLink) {
      await sendTelegram(botToken, chatId, "❌ <b>Usage:</b> <code>/dl &lt;link&gt;</code>");
      return;
    }

    // Send immediate loading message
    const loadingRes = await sendTelegram(
      botToken,
      chatId,
      "⏳ <b>Processing Best HD Video...</b>\nStarting GitHub Actions runner to download and remove watermark. Please wait ~2-3 minutes..."
    );

    const loadingMsgId = loadingRes ? loadingRes.message_id : 0;

    // Trigger GitHub Actions via repository_dispatch
    if (githubToken) {
      await triggerGitHubWorkflow(githubToken, githubRepo, targetLink, chatId, loadingMsgId);
    } else {
      console.warn("GITHUB_TOKEN not configured in Worker.");
    }
  }
}

// ---------------- Helper Functions ---------------- //

async function triggerGitHubWorkflow(token, repo, url, chatId, messageId) {
  const endpoint = `https://api.github.com/repos/${repo}/dispatches`;
  await fetch(endpoint, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${token}`,
      "User-Agent": "Cloudflare-Worker",
      "Accept": "application/vnd.github.v3+json",
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      event_type: "download_clean",
      client_payload: {
        url: url,
        chat_id: String(chatId),
        message_id: messageId
      }
    })
  });
}

async function getLatestRssItem() {
  try {
    const res = await fetch("https://animekhor.org/feed/", {
      headers: { "User-Agent": "Mozilla/5.0" }
    });
    const xmlText = await res.text();
    const itemMatch = xmlText.match(/<item>([\s\S]*?)<\/item>/);
    if (!itemMatch) return null;

    const titleMatch = itemMatch[1].match(/<title>([\s\S]*?)<\/title>/);
    const linkMatch = itemMatch[1].match(/<link>([\s\S]*?)<\/link>/);

    return {
      title: titleMatch ? titleMatch[1].replace(/<!\[CDATA\[(.*?)\]\]>/g, "$1").trim() : "",
      link: linkMatch ? linkMatch[1].trim() : ""
    };
  } catch (e) {
    return null;
  }
}

async function extractVideoLink(pageUrl) {
  if (pageUrl.includes("dailymotion.com")) return pageUrl;
  try {
    const res = await fetch(pageUrl, {
      headers: { "User-Agent": "Mozilla/5.0", "Referer": "https://animekhor.org/" }
    });
    const html = await res.text();
    const dmMatch = html.match(/(?:https?:)?\/\/(?:www\.|geo\.)?dailymotion\.com\/(?:embed\/video\/|player\.html\?video=)([\w-]+)/);
    if (dmMatch) {
      return `https://www.dailymotion.com/video/${dmMatch[1]}`;
    }
  } catch (e) {}
  return pageUrl;
}

function extractDmId(url) {
  const match = url.match(/dailymotion\.com\/(?:video\/|embed\/video\/|player\.html\?video=)([\w-]+)/);
  return match ? match[1] : "";
}

async function getDailymotionThumbnail(videoUrl) {
  const vidId = extractDmId(videoUrl);
  if (!vidId) return "";
  try {
    const res = await fetch(`https://api.dailymotion.com/video/${vidId}?fields=thumbnail_1080_url,thumbnail_720_url,thumbnail_large_url`);
    const data = await res.json();
    return data.thumbnail_1080_url || data.thumbnail_720_url || data.thumbnail_large_url || "";
  } catch (e) {
    return "";
  }
}

function cleanTitleForDisplay(rawTitle) {
  return rawTitle.replace(/\[?www\.AnimeKhor\.org\]?/gi, "").replace(/\s+/g, " ").trim();
}

async function sendTelegram(botToken, chatId, text) {
  const res = await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      text: text,
      parse_mode: "HTML",
      disable_web_page_preview: false
    })
  });
  const data = await res.json();
  return data.ok ? data.result : null;
}

async function sendTelegramPhoto(botToken, chatId, photoUrl, caption) {
  const res = await fetch(`https://api.telegram.org/bot${botToken}/sendPhoto`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      photo: photoUrl,
      caption: caption,
      parse_mode: "HTML"
    })
  });
  const data = await res.json();
  return data.ok ? data.result : null;
}

async function deleteTelegramMessage(botToken, chatId, messageId) {
  await fetch(`https://api.telegram.org/bot${botToken}/deleteMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, message_id: messageId })
  });
}

async function answerCallbackQuery(botToken, callbackQueryId, text) {
  await fetch(`https://api.telegram.org/bot${botToken}/answerCallbackQuery`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ callback_query_id: callbackQueryId, text: text })
  });
}

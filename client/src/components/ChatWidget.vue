<template>
  <div class="chat-widget">
    <Transition name="chat-panel">
      <div v-if="isOpen" class="chat-panel" role="dialog" aria-modal="false" :aria-label="t('chat.title')">
        <div class="chat-header">
          <h3 class="chat-title">{{ t('chat.title') }}</h3>
          <button class="chat-close-button" :aria-label="t('chat.close')" @click="closePanel">
            <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
              <path d="M15 5L5 15M5 5L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
            </svg>
          </button>
        </div>

        <div ref="messageListEl" class="chat-messages">
          <div v-for="message in messages" :key="message.id" class="chat-message" :class="message.role">
            <div class="chat-bubble">{{ message.text }}</div>
          </div>

          <div v-if="isTyping" class="chat-message assistant">
            <div class="chat-bubble chat-typing" :aria-label="t('chat.typing')">
              <span class="chat-typing-dot"></span>
              <span class="chat-typing-dot"></span>
              <span class="chat-typing-dot"></span>
            </div>
          </div>
        </div>

        <div class="chat-input-row">
          <input ref="inputEl" v-model="draft" type="text" class="chat-input" :placeholder="t('chat.placeholder')" @keyup.enter="sendMessage" />
          <button class="chat-send-button" :disabled="!draft.trim()" @click="sendMessage">
            {{ t('chat.send') }}
          </button>
        </div>
      </div>
    </Transition>

    <button v-if="!isOpen" class="chat-launcher" :aria-label="t('chat.open')" @click="openPanel">
      <svg width="26" height="26" viewBox="0 0 24 24" fill="none">
        <path d="M4 5.5C4 4.67 4.67 4 5.5 4h13c.83 0 1.5.67 1.5 1.5v9c0 .83-.67 1.5-1.5 1.5H9l-4 4v-4H5.5C4.67 16 4 15.33 4 14.5v-9Z" fill="currentColor" />
      </svg>
    </button>
  </div>
</template>

<script>
import { ref, nextTick, onBeforeUnmount, watch } from 'vue'
import { useI18n } from '../composables/useI18n'

let nextMessageId = 1

export default {
  name: 'ChatWidget',
  setup() {
    const { t } = useI18n()

    const isOpen = ref(false)
    const draft = ref('')
    const isTyping = ref(false)
    const messageListEl = ref(null)
    const inputEl = ref(null)
    let replyTimer = null

    const messages = ref([{ id: nextMessageId++, role: 'assistant', text: t('chat.greeting') }])

    const scrollToBottom = () => {
      nextTick(() => {
        if (messageListEl.value) {
          messageListEl.value.scrollTop = messageListEl.value.scrollHeight
        }
      })
    }

    const openPanel = () => {
      isOpen.value = true
      nextTick(() => {
        inputEl.value?.focus()
        scrollToBottom()
      })
    }

    const closePanel = () => {
      isOpen.value = false
    }

    const sendMessage = () => {
      const text = draft.value.trim()
      if (!text) return

      messages.value.push({ id: nextMessageId++, role: 'user', text })
      draft.value = ''
      scrollToBottom()

      isTyping.value = true
      if (replyTimer) clearTimeout(replyTimer)
      replyTimer = setTimeout(() => {
        isTyping.value = false
        messages.value.push({
          id: nextMessageId++,
          role: 'assistant',
          text: t('chat.connecting')
        })
        scrollToBottom()
        replyTimer = null
      }, 800)
    }

    const handleKeydown = event => {
      if (event.key === 'Escape' && isOpen.value) {
        closePanel()
      }
    }

    watch(isOpen, open => {
      if (open) {
        window.addEventListener('keydown', handleKeydown)
      } else {
        window.removeEventListener('keydown', handleKeydown)
      }
    })

    onBeforeUnmount(() => {
      if (replyTimer) {
        clearTimeout(replyTimer)
        replyTimer = null
      }
      window.removeEventListener('keydown', handleKeydown)
    })

    return {
      t,
      isOpen,
      draft,
      isTyping,
      messages,
      messageListEl,
      inputEl,
      openPanel,
      closePanel,
      sendMessage
    }
  }
}
</script>

<style scoped>
.chat-widget {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 500;
}

.chat-launcher {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: #0f172a;
  color: white;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.35);
  transition:
    transform 0.2s ease,
    background 0.2s ease;
}

.chat-launcher:hover {
  background: #1e293b;
  transform: translateY(-2px);
}

.chat-launcher:focus-visible {
  outline: 3px solid #2563eb;
  outline-offset: 3px;
}

.chat-panel {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 360px;
  height: 480px;
  max-width: calc(100vw - 32px);
  max-height: calc(100vh - 120px);
  background: white;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 20px 48px rgba(15, 23, 42, 0.2);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  background: #0f172a;
  color: white;
  flex-shrink: 0;
}

.chat-title {
  font-size: 1rem;
  font-weight: 700;
  margin: 0;
}

.chat-close-button {
  background: none;
  border: none;
  color: white;
  cursor: pointer;
  padding: 0.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition: background 0.2s ease;
}

.chat-close-button:hover {
  background: rgba(255, 255, 255, 0.15);
}

.chat-close-button:focus-visible {
  outline: 2px solid white;
  outline-offset: 2px;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
  background: #f8fafc;
}

.chat-message {
  display: flex;
}

.chat-message.user {
  justify-content: flex-end;
}

.chat-message.assistant {
  justify-content: flex-start;
}

.chat-bubble {
  max-width: 80%;
  padding: 0.625rem 0.875rem;
  border-radius: 12px;
  font-size: 0.875rem;
  line-height: 1.4;
  word-wrap: break-word;
}

.chat-message.user .chat-bubble {
  background: #0f172a;
  color: white;
  border-bottom-right-radius: 4px;
}

.chat-message.assistant .chat-bubble {
  background: #e2e8f0;
  color: #1e293b;
  border-bottom-left-radius: 4px;
}

.chat-typing {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.75rem 0.875rem;
}

.chat-typing-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #64748b;
  animation: chat-typing-bounce 1.2s infinite ease-in-out;
}

.chat-typing-dot:nth-child(2) {
  animation-delay: 0.15s;
}

.chat-typing-dot:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes chat-typing-bounce {
  0%,
  60%,
  100% {
    transform: translateY(0);
    opacity: 0.6;
  }
  30% {
    transform: translateY(-3px);
    opacity: 1;
  }
}

.chat-input-row {
  display: flex;
  gap: 0.5rem;
  padding: 0.75rem;
  border-top: 1px solid #e2e8f0;
  background: white;
  flex-shrink: 0;
}

.chat-input {
  flex: 1;
  padding: 0.625rem 0.75rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 0.875rem;
  font-family: inherit;
  color: #1e293b;
}

.chat-input:focus {
  outline: none;
  border-color: #0f172a;
}

.chat-send-button {
  padding: 0.625rem 1rem;
  background: #0f172a;
  color: white;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  font-size: 0.875rem;
  cursor: pointer;
  transition: background 0.2s ease;
  white-space: nowrap;
}

.chat-send-button:hover:not(:disabled) {
  background: #1e293b;
}

.chat-send-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chat-send-button:focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: 2px;
}

/* Panel transition */
.chat-panel-enter-active,
.chat-panel-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.chat-panel-enter-from,
.chat-panel-leave-to {
  opacity: 0;
  transform: translateY(12px) scale(0.98);
}
</style>

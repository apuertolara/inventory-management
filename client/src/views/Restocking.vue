<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
      <p class="filters-note">{{ t('restocking.filtersNotApplied') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else>
      <!-- Budget controls stay visible after the first load (even on a
           failed refresh) so a bad request doesn't strand the user
           without a way to retry by moving the slider. -->
      <div class="card budget-card">
        <div class="budget-label">{{ t('restocking.budget') }}</div>
        <div class="budget-value">{{ formatCurrency(budget, currentCurrency) }}</div>
        <input
          type="range"
          class="budget-slider"
          min="0"
          max="10000"
          step="50"
          v-model.number="budget"
          :aria-label="t('restocking.budgetInput')"
        />
        <div class="budget-range-labels">
          <span>{{ formatCurrency(0, currentCurrency) }}</span>
          <span>{{ formatCurrency(10000, currentCurrency) }}</span>
        </div>
        <input
          type="number"
          class="budget-number"
          min="0"
          max="10000"
          step="50"
          v-model.number="budgetNumberInput"
          :aria-label="t('restocking.budgetInput')"
        />
      </div>

      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.stats.totalCost') }}</div>
          <div class="stat-value">{{ formatCurrencyWithDecimals(data.total_cost || 0, currentCurrency, 2) }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.stats.remainingBudget') }}</div>
          <div class="stat-value">{{ formatCurrencyWithDecimals(data.remaining_budget || 0, currentCurrency, 2) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.stats.itemsCount') }}</div>
          <div class="stat-value">{{ data.item_count || 0 }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.stats.maxLeadTime') }}</div>
          <div class="stat-value">{{ t('restocking.days', { days: data.max_lead_time_days || 0 }) }}</div>
        </div>
      </div>

      <div class="card" :class="{ 'is-refreshing': refreshing }">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommendations') }}</h3>
        </div>

        <!-- A load error is shown inline here, without hiding a
             previously-loaded table, so the last good recommendations
             stay visible while the user retries. -->
        <div v-if="error" class="error">{{ error }}</div>

        <div v-if="!error && recommendations.length === 0" class="empty-state">
          {{ t('restocking.empty') }}
        </div>
        <template v-else-if="recommendations.length > 0">
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>{{ t('restocking.table.sku') }}</th>
                  <th>{{ t('restocking.table.item') }}</th>
                  <th>{{ t('restocking.table.trend') }}</th>
                  <th class="col-num">{{ t('restocking.table.current') }}</th>
                  <th class="col-num">{{ t('restocking.table.forecast') }}</th>
                  <th class="col-num">{{ t('restocking.table.gap') }}</th>
                  <th class="col-num">{{ t('restocking.table.quantity') }}</th>
                  <th class="col-num">{{ t('restocking.table.unitCost') }}</th>
                  <th class="col-num">{{ t('restocking.table.lineTotal') }}</th>
                  <th class="col-num">{{ t('restocking.table.leadTime') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="rec in recommendations" :key="rec.item_sku">
                  <td><strong>{{ rec.item_sku }}</strong></td>
                  <td>{{ translateProductName(rec.item_name) }}</td>
                  <td>
                    <span :class="['badge', rec.trend]">{{ t(`trends.${rec.trend}`) }}</span>
                  </td>
                  <td class="col-num">{{ rec.current_demand }}</td>
                  <td class="col-num">{{ rec.forecasted_demand }}</td>
                  <td class="col-num">{{ rec.demand_gap }}</td>
                  <td class="col-num">
                    {{ rec.recommended_quantity }}
                    <span v-if="rec.partial" class="badge warning">{{ t('restocking.partial') }}</span>
                  </td>
                  <td class="col-num">{{ formatCurrencyWithDecimals(rec.unit_cost, currentCurrency, 2) }}</td>
                  <td class="col-num">{{ formatCurrencyWithDecimals(rec.line_total, currentCurrency, 2) }}</td>
                  <td class="col-num">{{ t('restocking.days', { days: rec.lead_time_days }) }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="place-order-row">
            <button
              type="button"
              class="btn-primary"
              :disabled="placeOrderDisabled"
              @click="submitOrder"
            >
              {{ submitting ? t('restocking.placing') : t('restocking.placeOrder') }}
            </button>
          </div>
        </template>

        <div v-if="submitSuccess" class="success-banner">
          {{ t('restocking.success', { id: submitSuccess.id, date: formattedDeliveryDate }) }}
          <router-link to="/orders">{{ t('restocking.viewOrders') }}</router-link>
        </div>
        <div v-if="submitError" class="error">{{ submitError }}</div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrency, formatCurrencyWithDecimals } from '../utils/currency'

export default {
  name: 'Restocking',
  setup() {
    const { t, currentLocale, currentCurrency, translateProductName } = useI18n()

    const loading = ref(true)
    const refreshing = ref(false)
    const error = ref(null)
    const budget = ref(5000)
    const data = ref({})
    const submitting = ref(false)
    const submitSuccess = ref(null)
    const submitError = ref(null)

    // Guards against out-of-order responses: only the most recently issued
    // request is allowed to update state, so a slow earlier response can't
    // overwrite a newer one.
    let requestSeq = 0
    let debounceTimer = null

    const recommendations = computed(() => data.value.recommendations || [])

    const placeOrderDisabled = computed(() => {
      return loading.value || refreshing.value || submitting.value ||
        recommendations.value.length === 0 || !!submitSuccess.value || !!error.value
    })

    const formattedDeliveryDate = computed(() => {
      if (!submitSuccess.value) return '-'
      const date = new Date(submitSuccess.value.expected_delivery)
      if (isNaN(date.getTime())) return '-'
      const locale = currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'
      return date.toLocaleDateString(locale, { year: 'numeric', month: 'short', day: 'numeric' })
    })

    // Number input mirrors the slider value, clamped to the same 0-10000 range.
    const budgetNumberInput = computed({
      get: () => budget.value,
      set: (val) => {
        // v-model.number passes the raw string back unchanged when it can't
        // parse it (e.g. an emptied input), so Number.isNaN(val) never
        // catches it. Parse explicitly and bail out on non-finite results
        // instead of letting Math.max/min coerce it into 0.
        const n = typeof val === 'number' ? val : parseFloat(val)
        if (!Number.isFinite(n)) return
        budget.value = Math.min(10000, Math.max(0, n))
      }
    })

    const loadRecommendations = async ({ isInitial = false } = {}) => {
      const seq = ++requestSeq
      if (isInitial) {
        loading.value = true
      } else {
        refreshing.value = true
      }
      error.value = null

      try {
        const response = await api.getRestockingRecommendations(budget.value)
        // Ignore stale responses if a newer request has since been issued.
        if (seq !== requestSeq) return
        data.value = response
      } catch (err) {
        if (seq !== requestSeq) return
        error.value = t('restocking.loadError')
        console.error(err)
      } finally {
        if (seq === requestSeq) {
          loading.value = false
          refreshing.value = false
        }
      }
    }

    watch(budget, () => {
      submitSuccess.value = null
      submitError.value = null

      // Mark the displayed data as stale the instant the budget changes,
      // not only once the debounce timer fires. Otherwise there's a window
      // (up to 300ms) where the table/stats still reflect the old budget
      // but the button and dimmed style act as if they're current.
      refreshing.value = true

      if (debounceTimer) clearTimeout(debounceTimer)
      debounceTimer = setTimeout(() => {
        loadRecommendations()
      }, 300)
    })

    onBeforeUnmount(() => {
      if (debounceTimer) clearTimeout(debounceTimer)
    })

    const submitOrder = async () => {
      if (placeOrderDisabled.value) return
      // Belt-and-suspenders guard: if the loaded recommendations don't
      // match the currently displayed budget (e.g. a stale click slipping
      // in right as the budget changes), don't submit against mismatched data.
      if (data.value.budget !== budget.value) return
      submitting.value = true
      submitError.value = null

      try {
        // Use the budget the displayed recommendations were computed for,
        // not a potentially newer slider value.
        const orderBudget = data.value.budget !== undefined ? data.value.budget : budget.value
        const items = recommendations.value.map(rec => ({
          item_sku: rec.item_sku,
          quantity: rec.recommended_quantity
        }))
        const result = await api.createRestockingOrder({ items, budget: orderBudget })
        submitSuccess.value = result
      } catch (err) {
        const detail = err.response && err.response.data && err.response.data.detail
        if (typeof detail === 'string') {
          submitError.value = detail
        } else if (Array.isArray(detail) && detail.length > 0) {
          submitError.value = detail.map(d => d.msg || JSON.stringify(d)).join('; ')
        } else {
          submitError.value = t('restocking.submitError')
        }
      } finally {
        submitting.value = false
      }
    }

    onMounted(() => loadRecommendations({ isInitial: true }))

    return {
      t,
      currentCurrency,
      translateProductName,
      formatCurrency,
      formatCurrencyWithDecimals,
      loading,
      refreshing,
      error,
      budget,
      budgetNumberInput,
      data,
      recommendations,
      submitting,
      submitSuccess,
      submitError,
      placeOrderDisabled,
      formattedDeliveryDate,
      submitOrder
    }
  }
}
</script>

<style scoped>
.filters-note {
  color: #94a3b8;
  font-size: 0.813rem;
  margin-top: 0.25rem;
}

.budget-card {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.budget-label {
  color: #64748b;
  font-size: 0.875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.budget-value {
  font-size: 2.25rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
}

.budget-slider {
  width: 100%;
  accent-color: #3b82f6;
}

.budget-range-labels {
  display: flex;
  justify-content: space-between;
  color: #94a3b8;
  font-size: 0.75rem;
}

.budget-number {
  margin-top: 0.5rem;
  width: 140px;
  padding: 0.5rem 0.625rem;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 0.875rem;
}

.col-num {
  text-align: right;
}

.is-refreshing {
  opacity: 0.6;
  transition: opacity 0.15s ease;
}

.empty-state {
  padding: 2rem;
  text-align: center;
  color: #64748b;
}

.place-order-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 1rem;
}

.btn-primary {
  background: #3b82f6;
  color: white;
  border: none;
  padding: 0.625rem 1.5rem;
  border-radius: 6px;
  font-size: 0.938rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease;
}

.btn-primary:hover:not(:disabled) {
  background: #2563eb;
}

.btn-primary:disabled {
  background: #cbd5e1;
  color: #94a3b8;
  cursor: not-allowed;
}

.success-banner {
  margin-top: 1rem;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  color: #166534;
  padding: 1rem;
  border-radius: 8px;
  font-size: 0.938rem;
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
}

.success-banner a {
  color: #166534;
  font-weight: 600;
  text-decoration: underline;
}
</style>

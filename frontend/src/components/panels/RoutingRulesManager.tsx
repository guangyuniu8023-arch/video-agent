import { useState, useEffect, useCallback } from 'react'
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import {
  fetchRoutingRules,
  createRoutingRule,
  updateRoutingRule,
  toggleRoutingRule,
  deleteRoutingRule,
  reorderRoutingRules,
} from '@/services/api'

interface RoutingRule {
  id: number
  name: string
  description: string
  priority: number
  enabled: boolean
  target_type: string
  target_skill: string | null
  skip_agents: string[]
  match_description: string
}

export function RoutingRulesManager() {
  const [rules, setRules] = useState<RoutingRule[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingRule, setEditingRule] = useState<RoutingRule | null>(null)
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null)

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  )

  const loadRules = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchRoutingRules()
      setRules(data.rules)
    } catch {
      setMessage({ text: '加载路由规则失败', type: 'error' })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadRules() }, [loadRules])

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return

    const oldIndex = rules.findIndex(r => r.id === active.id)
    const newIndex = rules.findIndex(r => r.id === over.id)
    const newRules = arrayMove(rules, oldIndex, newIndex)
    setRules(newRules)

    try {
      await reorderRoutingRules(newRules.map(r => r.id))
    } catch {
      setMessage({ text: '排序更新失败', type: 'error' })
      loadRules()
    }
  }

  const handleToggle = async (ruleId: number, enabled: boolean) => {
    try {
      await toggleRoutingRule(ruleId, !enabled)
      setRules(prev => prev.map(r => r.id === ruleId ? { ...r, enabled: !enabled } : r))
    } catch {
      setMessage({ text: '状态切换失败', type: 'error' })
    }
  }

  const handleDelete = async (ruleId: number) => {
    if (!confirm('确定删除这条路由规则？')) return
    try {
      await deleteRoutingRule(ruleId)
      setRules(prev => prev.filter(r => r.id !== ruleId))
      setMessage({ text: '已删除', type: 'success' })
      setTimeout(() => setMessage(null), 2000)
    } catch {
      setMessage({ text: '删除失败', type: 'error' })
    }
  }

  const handleSaveRule = async (data: Partial<RoutingRule>) => {
    try {
      if (editingRule) {
        const updated = await updateRoutingRule(editingRule.id, data)
        setRules(prev => prev.map(r => r.id === editingRule.id ? updated : r))
      } else {
        const created = await createRoutingRule(data as RoutingRule)
        setRules(prev => [...prev, created])
      }
      setShowForm(false)
      setEditingRule(null)
      setMessage({ text: editingRule ? '已更新' : '已创建', type: 'success' })
      setTimeout(() => setMessage(null), 2000)
    } catch {
      setMessage({ text: '保存失败', type: 'error' })
    }
  }

  if (loading) {
    return <div className="p-4 text-sm text-gray-500">加载中...</div>
  }

  return (
    <div className="flex flex-col h-full">
      {/* 头部 */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border shrink-0">
        <span className="text-xs text-gray-400">
          {rules.length} 条规则 ({rules.filter(r => r.enabled).length} 启用)
        </span>
        <button
          onClick={() => { setEditingRule(null); setShowForm(true) }}
          className="text-[10px] px-2 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white transition-colors"
        >
          + 新增规则
        </button>
      </div>

      {message && (
        <div className={`px-3 py-1.5 text-xs shrink-0 ${
          message.type === 'success' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'
        }`}>
          {message.text}
        </div>
      )}

      {/* 表单 */}
      {showForm && (
        <RuleForm
          initial={editingRule}
          onSave={handleSaveRule}
          onCancel={() => { setShowForm(false); setEditingRule(null) }}
        />
      )}

      {/* 规则列表 (可拖拽排序) */}
      <div className="flex-1 overflow-auto">
        {rules.length === 0 ? (
          <div className="p-4 text-center">
            <p className="text-xs text-gray-500 mb-2">暂无路由规则</p>
            <p className="text-[10px] text-gray-600">所有请求将走完整链路 (full_pipeline)</p>
          </div>
        ) : (
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={rules.map(r => r.id)} strategy={verticalListSortingStrategy}>
              <div className="divide-y divide-border">
                {rules.map((rule) => (
                  <SortableRuleItem
                    key={rule.id}
                    rule={rule}
                    onToggle={() => handleToggle(rule.id, rule.enabled)}
                    onEdit={() => { setEditingRule(rule); setShowForm(true) }}
                    onDelete={() => handleDelete(rule.id)}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        )}
      </div>
    </div>
  )
}

function SortableRuleItem({ rule, onToggle, onEdit, onDelete }: {
  rule: RoutingRule
  onToggle: () => void
  onEdit: () => void
  onDelete: () => void
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: rule.id })
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  const targetLabels: Record<string, string> = {
    full_pipeline: '完整链路',
    skip_to_producer: '跳过 Planner',
    skip_to_editor: '跳过 P+P',
    direct_skill: '直接技能',
  }

  return (
    <div ref={setNodeRef} style={style} className="flex items-center gap-2 px-3 py-2.5 hover:bg-white/5">
      {/* 拖拽手柄 */}
      <button
        {...attributes}
        {...listeners}
        className="text-gray-600 hover:text-gray-400 cursor-grab active:cursor-grabbing shrink-0"
      >
        ≡
      </button>

      {/* 信息 */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={`text-sm font-medium ${rule.enabled ? 'text-gray-200' : 'text-gray-500'}`}>
            {rule.name}
          </span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-900/50 text-purple-400">
            {targetLabels[rule.target_type] ?? rule.target_type}
          </span>
        </div>
        {rule.match_description && (
          <p className="text-[10px] text-gray-500 mt-0.5 truncate">{rule.match_description}</p>
        )}
      </div>

      {/* 操作 */}
      <button
        onClick={onToggle}
        className={`text-[10px] px-2 py-1 rounded transition-colors shrink-0 ${
          rule.enabled
            ? 'bg-green-900/50 text-green-400 hover:bg-green-900/70'
            : 'bg-gray-700 text-gray-500 hover:bg-gray-600'
        }`}
      >
        {rule.enabled ? '启用' : '禁用'}
      </button>
      <button
        onClick={onEdit}
        className="text-[10px] px-2 py-1 rounded bg-gray-700 hover:bg-gray-600 text-gray-300 transition-colors shrink-0"
      >
        编辑
      </button>
      <button
        onClick={onDelete}
        className="text-[10px] px-2 py-1 rounded bg-red-900/50 hover:bg-red-900/70 text-red-400 transition-colors shrink-0"
      >
        删除
      </button>
    </div>
  )
}

function RuleForm({ initial, onSave, onCancel }: {
  initial: RoutingRule | null
  onSave: (data: Partial<RoutingRule>) => void
  onCancel: () => void
}) {
  const [name, setName] = useState(initial?.name ?? '')
  const [targetType, setTargetType] = useState(initial?.target_type ?? 'full_pipeline')
  const [matchDesc, setMatchDesc] = useState(initial?.match_description ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSave({
      name,
      target_type: targetType,
      match_description: matchDesc,
      description,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="border-b border-border p-3 space-y-2 bg-surface-light shrink-0">
      <div>
        <label className="text-[10px] text-gray-400 block mb-0.5">规则名称</label>
        <input
          value={name}
          onChange={e => setName(e.target.value)}
          required
          className="w-full bg-gray-800 text-sm text-gray-200 rounded px-2 py-1.5 border border-gray-600 focus:border-blue-500 focus:outline-none"
          placeholder="例: 直接拼接视频"
        />
      </div>
      <div>
        <label className="text-[10px] text-gray-400 block mb-0.5">路由目标</label>
        <select
          value={targetType}
          onChange={e => setTargetType(e.target.value)}
          className="w-full bg-gray-800 text-sm text-gray-200 rounded px-2 py-1.5 border border-gray-600 focus:border-blue-500 focus:outline-none"
        >
          <option value="full_pipeline">完整链路 (全部 Agent)</option>
          <option value="skip_to_producer">跳过 Planner → 直接到 Producer</option>
          <option value="skip_to_editor">跳过 Planner+Producer → 直接到 Editor</option>
          <option value="direct_skill">直接调用单个技能</option>
        </select>
      </div>
      <div>
        <label className="text-[10px] text-gray-400 block mb-0.5">匹配描述 (供 LLM 判断)</label>
        <textarea
          value={matchDesc}
          onChange={e => setMatchDesc(e.target.value)}
          rows={2}
          className="w-full bg-gray-800 text-xs text-gray-200 rounded px-2 py-1.5 border border-gray-600 focus:border-blue-500 focus:outline-none resize-none"
          placeholder="描述什么类型的用户请求应该匹配此规则"
        />
      </div>
      <div>
        <label className="text-[10px] text-gray-400 block mb-0.5">说明 (可选)</label>
        <input
          value={description}
          onChange={e => setDescription(e.target.value)}
          className="w-full bg-gray-800 text-sm text-gray-200 rounded px-2 py-1.5 border border-gray-600 focus:border-blue-500 focus:outline-none"
          placeholder="规则用途说明"
        />
      </div>
      <div className="flex gap-2 pt-1">
        <button
          type="submit"
          className="text-xs px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white transition-colors"
        >
          {initial ? '更新' : '创建'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="text-xs px-3 py-1.5 rounded bg-gray-700 hover:bg-gray-600 text-gray-300 transition-colors"
        >
          取消
        </button>
      </div>
    </form>
  )
}

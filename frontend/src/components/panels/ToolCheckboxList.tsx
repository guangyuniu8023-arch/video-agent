import { useEffect, useState, useCallback } from 'react'
import {
  fetchAgentTools, fetchSkillContent, updateSkillContent, updateAgentTools,
  type ToolEntry,
} from '@/services/api'
import { FileText, Save, X, Plus, Wrench, ChevronDown, ChevronRight } from 'lucide-react'

interface ToolCheckboxListProps {
  agentId: string
}

export function ToolCheckboxList({ agentId }: ToolCheckboxListProps) {
  const [tools, setTools] = useState<ToolEntry[]>([])
  const [currentTools, setCurrentTools] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [editingSkill, setEditingSkill] = useState<string | null>(null)
  const [skillContent, setSkillContent] = useState('')
  const [skillSaving, setSkillSaving] = useState(false)
  const [expandedTool, setExpandedTool] = useState<string | null>(null)
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [showAddSkill, setShowAddSkill] = useState(false)
  const [allSkills, setAllSkills] = useState<Array<{ name: string; title: string; description: string }>>([])
  const [allTools, setAllTools] = useState<string[]>([])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchAgentTools(agentId)
      const skills = (data.tools ?? []).filter(t => t.type === 'skill')
      setTools(skills)
      setCurrentTools(data.current_tools)
      setAllTools(data.current_tools)
      setDirty(false)

      const res = await fetch('/api/admin/skills')
      if (res.ok) {
        const skillsData = await res.json()
        setAllSkills((skillsData.skills || []).map((s: Record<string, string>) => ({
          name: s.name, title: s.title || s.name, description: s.description || '',
        })))
      }
    } catch (err) {
      console.error('Failed to load tools:', err)
    } finally {
      setLoading(false)
    }
  }, [agentId])

  useEffect(() => { load() }, [load])

  const toggleSkill = useCallback((name: string) => {
    setCurrentTools(prev => {
      setDirty(true)
      return prev.includes(name) ? prev.filter(t => t !== name) : [...prev, name]
    })
  }, [])

  const handleSave = useCallback(async () => {
    setSaving(true)
    try {
      const subAgentIds = allTools.filter(t => !tools.some(s => s.name === t) && !allSkills.some(s => s.name === t))
      await updateAgentTools(agentId, [...currentTools, ...subAgentIds])
      setDirty(false)
      await load()
    } catch (err) {
      console.error('Failed to save:', err)
    } finally {
      setSaving(false)
    }
  }, [agentId, currentTools, allTools, tools, allSkills, load])

  const addSkillToAgent = useCallback(async (skillName: string) => {
    const newTools = [...currentTools, skillName]
    setCurrentTools(newTools)
    setDirty(true)
    setShowAddSkill(false)

    const subAgentIds = allTools.filter(t => !tools.some(s => s.name === t) && !allSkills.some(s => s.name === t))
    try {
      await updateAgentTools(agentId, [...newTools, ...subAgentIds])
      setDirty(false)
      await load()
    } catch (err) {
      console.error('Failed to add skill:', err)
    }
  }, [agentId, currentTools, allTools, tools, allSkills, load])

  const openSkillEditor = useCallback(async (skillName: string) => {
    try {
      const data = await fetchSkillContent(skillName)
      setSkillContent(data.content)
      setEditingSkill(skillName)
    } catch (err) {
      console.error('Failed to load skill content:', err)
    }
  }, [])

  const handleSkillSave = useCallback(async () => {
    if (!editingSkill) return
    setSkillSaving(true)
    try {
      await updateSkillContent(editingSkill, skillContent)
      setEditingSkill(null)
      await load()
    } catch (err) {
      console.error('Failed to save skill:', err)
    } finally {
      setSkillSaving(false)
    }
  }, [editingSkill, skillContent, load])

  if (loading) return <div className="p-4 text-gray-500 text-sm">加载中...</div>

  if (editingSkill) {
    return (
      <div className="h-full flex flex-col">
        <div className="px-4 py-2 border-b border-border flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <FileText size={14} className="text-blue-400" />
            <span className="text-xs font-medium text-white">{editingSkill}</span>
            <span className="text-[10px] text-gray-500">SKILL.md</span>
          </div>
          <div className="flex items-center gap-1.5">
            <button onClick={handleSkillSave} disabled={skillSaving}
              className="text-[10px] px-2 py-1 rounded bg-green-600 text-white hover:bg-green-500 disabled:opacity-50 flex items-center gap-1">
              <Save size={10} />{skillSaving ? '保存中...' : '保存'}
            </button>
            <button onClick={() => setEditingSkill(null)} className="p-1 rounded hover:bg-gray-700 text-gray-400">
              <X size={14} />
            </button>
          </div>
        </div>
        <textarea value={skillContent} onChange={(e) => setSkillContent(e.target.value)}
          className="flex-1 bg-gray-900 text-gray-200 text-xs font-mono p-4 resize-none focus:outline-none leading-relaxed" spellCheck={false} />
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      <div className="px-4 py-2 border-b border-border flex items-center justify-between shrink-0">
        <span className="text-xs text-gray-400">
          {tools.length} 个 Skill
        </span>
        <div className="flex items-center gap-1.5">
          {dirty && (
            <button onClick={handleSave} disabled={saving}
              className="text-[10px] px-2.5 py-1 rounded bg-primary text-white hover:bg-blue-600 disabled:opacity-50 flex items-center gap-1">
              <Save size={10} />{saving ? '保存中...' : '保存'}
            </button>
          )}
          <button onClick={() => setShowAddSkill(!showAddSkill)}
            className="text-[10px] px-2 py-1 rounded bg-green-600/20 text-green-400 hover:bg-green-600/30 flex items-center gap-0.5">
            <Plus size={10} />Skill
          </button>
        </div>
      </div>

      {showAddSkill && (
        <div className="px-3 py-2 border-b border-green-500/20 bg-green-950/10 shrink-0">
          <div className="text-[10px] text-gray-400 mb-1.5">选择要添加的 Skill:</div>
          <div className="max-h-32 overflow-auto space-y-1">
            {allSkills
              .filter(s => !currentTools.includes(s.name))
              .map(s => (
                <button key={s.name} onClick={() => addSkillToAgent(s.name)}
                  className="w-full text-left text-xs px-2 py-1.5 rounded hover:bg-white/5 flex items-center gap-2 transition-colors">
                  <Wrench size={10} className="text-gray-500 shrink-0" />
                  <span className="text-white">{s.title}</span>
                  <span className="text-[10px] text-gray-500 font-mono">{s.name}</span>
                </button>
              ))}
            {allSkills.filter(s => !currentTools.includes(s.name)).length === 0 && (
              <div className="text-[10px] text-gray-500 py-2 text-center">所有 Skill 已添加</div>
            )}
          </div>
        </div>
      )}

      <div className="flex-1 overflow-auto p-3 space-y-1.5">
        {tools.map((t) => {
          const enabled = currentTools.includes(t.name)
          const isExpanded = expandedTool === t.name

          return (
            <div key={t.name} className={`rounded-lg border overflow-hidden ${enabled ? 'border-green-500/30' : 'border-border'}`}>
              <div className="flex items-center gap-2 px-3 py-2 bg-surface-light">
                <input type="checkbox" checked={enabled} onChange={() => toggleSkill(t.name)}
                  className="rounded border-gray-600 bg-gray-800 text-primary focus:ring-0 focus:ring-offset-0" />
                <button onClick={() => setExpandedTool(isExpanded ? null : t.name)}
                  className="flex items-center gap-1 flex-1 min-w-0 text-left">
                  {isExpanded ? <ChevronDown size={10} className="text-gray-500" /> : <ChevronRight size={10} className="text-gray-500" />}
                  <span className="text-xs font-medium text-white">{t.title || t.name}</span>
                  {t.title && <span className="text-[10px] text-gray-500 font-mono">{t.name}</span>}
                </button>
                {t.trigger && t.trigger.length > 0 && t.trigger[0] !== 'always' ? (
                  <span className="text-[9px] px-1.5 py-0.5 rounded bg-yellow-900/40 text-yellow-400 shrink-0">条件</span>
                ) : (
                  <span className="text-[9px] px-1.5 py-0.5 rounded bg-green-900/40 text-green-400 shrink-0">常驻</span>
                )}
                <button onClick={() => openSkillEditor(t.name)}
                  className="p-1 rounded hover:bg-white/10 text-gray-500 hover:text-white transition-colors shrink-0" title="编辑 SKILL.md">
                  <FileText size={10} />
                </button>
              </div>
              {isExpanded && (
                <div className="px-3 py-2 text-[11px] space-y-1">
                  <p className="text-gray-400">{t.description}</p>
                  {t.trigger && t.trigger.length > 0 && t.trigger[0] !== 'always' && (
                    <div className="text-gray-500">
                      触发: {t.trigger.map((tr, i) => <span key={i} className="text-yellow-400/80">• {tr} </span>)}
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}

        {tools.length === 0 && (
          <div className="text-center text-gray-500 text-xs py-8">无可用 Skill</div>
        )}
      </div>
    </div>
  )
}

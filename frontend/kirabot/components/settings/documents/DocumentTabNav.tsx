import React from 'react';
import { Settings, FileText, ClipboardList, CalendarDays, Presentation, Award } from 'lucide-react';

export type DocumentTab = 'profile' | 'rfp' | 'proposal' | 'execution_plan' | 'presentation' | 'track_record';

interface Props {
  activeTab: DocumentTab;
  onTabChange: (tab: DocumentTab) => void;
}

const TABS: Array<{ id: DocumentTab; label: string; icon: React.ElementType }> = [
  { id: 'profile', label: '회사 프로필', icon: Settings },
  { id: 'rfp', label: 'RFP 분석', icon: ClipboardList },
  { id: 'proposal', label: '제안서', icon: FileText },
  { id: 'execution_plan', label: 'WBS', icon: CalendarDays },
  { id: 'presentation', label: 'PPT', icon: Presentation },
  { id: 'track_record', label: '실적기술서', icon: Award },
];

export default function DocumentTabNav({ activeTab, onTabChange }: Props) {
  return (
    <nav className="w-40 shrink-0 border-r border-slate-200 py-4 px-2 space-y-0.5">
      <h3 className="px-3 pb-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">문서</h3>
      {TABS.map((tab) => {
        const Icon = tab.icon;
        const isActive = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`w-full flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors ${
              isActive
                ? 'bg-kira-50 text-kira-700 font-semibold border-l-2 border-kira-500 -ml-px'
                : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
            }`}
          >
            <Icon size={16} className="shrink-0" />
            <span className="flex-1 text-left">{tab.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

import React, { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Settings, Home, LogOut } from 'lucide-react';

interface ProfilePopoverProps {
  open: boolean;
  onClose: () => void;
  email: string;
  onLogout: () => void;
  onHome: () => void;
}

const ProfilePopover: React.FC<ProfilePopoverProps> = ({ open, onClose, email, onLogout, onHome }) => {
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleKey);
    };
  }, [open, onClose]);

  const items = [
    { label: '설정', icon: Settings, onClick: () => { navigate('/settings'); onClose(); } },
    { label: '홈으로', icon: Home, onClick: () => { onHome(); onClose(); } },
  ];

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          ref={ref}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 8 }}
          transition={{ duration: 0.15 }}
          className="absolute bottom-full left-2 right-2 mb-2 rounded-lg bg-gray-800 shadow-xl border border-white/10 overflow-hidden z-50"
        >
          <div className="px-3 py-2.5 text-xs text-slate-400 truncate border-b border-white/10">
            {email}
          </div>
          <div className="py-1">
            {items.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.label}
                  type="button"
                  onClick={item.onClick}
                  className="flex w-full items-center gap-2.5 px-3 py-2 text-sm text-slate-300 hover:bg-gray-700 transition-colors"
                >
                  <Icon size={15} className="shrink-0" />
                  {item.label}
                </button>
              );
            })}
          </div>
          <div className="border-t border-white/10 py-1">
            <button
              type="button"
              onClick={() => { onLogout(); onClose(); }}
              className="flex w-full items-center gap-2.5 px-3 py-2 text-sm text-red-400 hover:bg-gray-700 transition-colors"
            >
              <LogOut size={15} className="shrink-0" />
              로그아웃
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default ProfilePopover;

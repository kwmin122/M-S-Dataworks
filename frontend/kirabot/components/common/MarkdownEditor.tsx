import React, { useRef, useEffect } from 'react';
import {
  MDXEditor,
  headingsPlugin,
  listsPlugin,
  quotePlugin,
  thematicBreakPlugin,
  markdownShortcutPlugin,
  toolbarPlugin,
  linkPlugin,
  linkDialogPlugin,
  tablePlugin,
  BoldItalicUnderlineToggles,
  ListsToggle,
  BlockTypeSelect,
  CreateLink,
  InsertTable,
  UndoRedo,
  type MDXEditorMethods,
} from '@mdxeditor/editor';
import '@mdxeditor/editor/style.css';

interface Props {
  value: string;
  onChange: (md: string) => void;
  readOnly?: boolean;
  className?: string;
}

export default function MarkdownEditor({ value, onChange, readOnly, className }: Props) {
  const editorRef = useRef<MDXEditorMethods>(null);

  // Sync external value changes (e.g. after rollback/reload)
  useEffect(() => {
    if (editorRef.current) {
      const current = editorRef.current.getMarkdown();
      if (current !== value) {
        editorRef.current.setMarkdown(value);
      }
    }
  }, [value]);

  return (
    <div className={`mdx-editor-wrapper rounded-lg border border-slate-300 overflow-hidden ${className ?? ''}`}>
      <MDXEditor
        ref={editorRef}
        markdown={value}
        onChange={onChange}
        readOnly={readOnly}
        plugins={[
          headingsPlugin({ allowedHeadingLevels: [2, 3, 4] }),
          listsPlugin(),
          quotePlugin(),
          thematicBreakPlugin(),
          markdownShortcutPlugin(),
          linkPlugin(),
          linkDialogPlugin(),
          tablePlugin(),
          ...(readOnly
            ? []
            : [
                toolbarPlugin({
                  toolbarContents: () => (
                    <>
                      <UndoRedo />
                      <BlockTypeSelect />
                      <BoldItalicUnderlineToggles />
                      <ListsToggle />
                      <CreateLink />
                      <InsertTable />
                    </>
                  ),
                }),
              ]),
        ]}
      />
    </div>
  );
}

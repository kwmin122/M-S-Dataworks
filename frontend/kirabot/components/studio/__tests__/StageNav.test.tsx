import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import StageNav from '../StageNav';
import { STUDIO_STAGES } from '../../../services/studioApi';
import type { StudioStage } from '../../../services/studioApi';

describe('StageNav', () => {
  it('renders all 7 stages', () => {
    const onChange = vi.fn();
    render(<StageNav currentStage="rfp" onStageChange={onChange} />);

    for (const stage of STUDIO_STAGES) {
      expect(screen.getByTestId(`stage-${stage.key}`)).toBeInTheDocument();
      expect(screen.getByText(stage.label)).toBeInTheDocument();
    }
  });

  it('highlights the current stage', () => {
    const onChange = vi.fn();
    render(<StageNav currentStage="company" onStageChange={onChange} />);

    const companyBtn = screen.getByTestId('stage-company');
    expect(companyBtn).toHaveAttribute('aria-current', 'step');

    // Other stages should NOT have aria-current
    const rfpBtn = screen.getByTestId('stage-rfp');
    expect(rfpBtn).not.toHaveAttribute('aria-current');
  });

  it('calls onStageChange when clicking a stage', () => {
    const onChange = vi.fn();
    render(<StageNav currentStage="rfp" onStageChange={onChange} />);

    fireEvent.click(screen.getByTestId('stage-package'));
    expect(onChange).toHaveBeenCalledWith('package');
  });

  it('shows numbered badges for each stage', () => {
    const onChange = vi.fn();
    render(<StageNav currentStage="rfp" onStageChange={onChange} />);

    // Stages are numbered 1-7
    for (let i = 1; i <= 7; i++) {
      expect(screen.getByText(String(i))).toBeInTheDocument();
    }
  });
});

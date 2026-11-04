import type { DealStage, PipelineCard, PipelineOut } from "@/api/types";

export function findCard(pipeline: PipelineOut | undefined, dealId: number): PipelineCard | undefined {
  for (const column of pipeline?.columns ?? []) {
    const card = column.deals.find((deal) => deal.id === dealId);
    if (card) return card;
  }
  return undefined;
}

/**
 * Optimistic move: returns a new pipeline with the card at the top of `to`. Column
 * count/amount_minor cover every deal (the board only lists up to 100 per column), so
 * they are adjusted by ±1 and ±the card's amount rather than re-summed. Never mutates.
 * `amountMinor` (if given) is the deal's new value, e.g. a cash sale recorded on the move.
 */
export function moveCard(
  pipeline: PipelineOut,
  dealId: number,
  to: DealStage,
  amountMinor?: number,
): PipelineOut {
  const card = findCard(pipeline, dealId);
  if (!card) return pipeline;
  const oldAmount = card.amount_minor ?? 0;
  const newAmount = amountMinor ?? oldAmount;
  const moved: PipelineCard = {
    ...card,
    stage: to,
    amount_minor: amountMinor ?? card.amount_minor,
    updated_at: new Date().toISOString(),
  };
  if (card.stage === to) {
    if (newAmount === oldAmount) return pipeline;
    return {
      ...pipeline,
      columns: pipeline.columns.map((column) =>
        column.stage === to
          ? {
              ...column,
              amount_minor: column.amount_minor - oldAmount + newAmount,
              deals: column.deals.map((d) => (d.id === dealId ? moved : d)),
            }
          : column,
      ),
    };
  }
  return {
    ...pipeline,
    columns: pipeline.columns.map((column) => {
      if (column.stage === card.stage) {
        return {
          ...column,
          count: Math.max(0, column.count - 1),
          amount_minor: Math.max(0, column.amount_minor - oldAmount),
          deals: column.deals.filter((d) => d.id !== dealId),
        };
      }
      if (column.stage === to) {
        return {
          ...column,
          count: column.count + 1,
          amount_minor: column.amount_minor + newAmount,
          deals: [moved, ...column.deals],
        };
      }
      return column;
    }),
  };
}

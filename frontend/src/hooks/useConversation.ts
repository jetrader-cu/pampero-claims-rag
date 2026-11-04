import { useCallback, useEffect, useRef, useState } from "react";
import { askQuestion } from "../api/client";
import { useSession } from "../context/useSession";
import {
  ANSWER_ERROR_COPY,
  classifyAnswerError,
  DEFAULT_RETRY_AFTER_S,
  type AnswerFailure,
} from "../lib/errors";
import type { AnswerResponse } from "../types";
import { SESSION_EXPIRED } from "./useDocuments";

/** Tras 8 s se avisa de la demora; a los 45 s el cliente aborta (el backend corta antes). */
const SLOW_AFTER_MS = 8000;
const CLIENT_TIMEOUT_MS = 45000;
const TOP_K = 8;

export interface Turn {
  id: string;
  question: string;
  askedAt: Date;
  state: "loading" | "answered" | "failed";
  slow: boolean;
  answer?: AnswerResponse;
  failure?: AnswerFailure;
  /** Instante del reintento automático programado, si lo hay. */
  autoRetryAt: number | null;
  /** Solo un reintento automático por turno: después decide el usuario. */
  autoRetried: boolean;
}

let sequence = 0;

export function useConversation() {
  const { session, expire } = useSession();
  const apiKey = session?.apiKey ?? "";
  const [turns, setTurns] = useState<Turn[]>([]);
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>[]>());
  const controllers = useRef(new Map<string, AbortController>());

  const update = useCallback((id: string, change: Partial<Turn>) => {
    setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, ...change } : t)));
  }, []);

  const clearTimers = useCallback((id: string) => {
    timers.current.get(id)?.forEach(clearTimeout);
    timers.current.delete(id);
  }, []);

  const addTimer = useCallback((id: string, fn: () => void, ms: number) => {
    const handle = setTimeout(fn, ms);
    timers.current.set(id, [...(timers.current.get(id) ?? []), handle]);
  }, []);

  const run = useCallback(
    async (id: string, question: string, autoRetried: boolean) => {
      clearTimers(id);
      controllers.current.get(id)?.abort();
      const controller = new AbortController();
      controllers.current.set(id, controller);
      update(id, { state: "loading", slow: false, failure: undefined, autoRetryAt: null, autoRetried });

      addTimer(id, () => update(id, { slow: true }), SLOW_AFTER_MS);
      addTimer(id, () => controller.abort(), CLIENT_TIMEOUT_MS);

      try {
        const answer = await askQuestion({ question, top_k: TOP_K }, apiKey, controller.signal);
        clearTimers(id);
        update(id, { state: "answered", answer });
      } catch (err) {
        clearTimers(id);
        const failure = classifyAnswerError(err);
        if (failure.kind === "unauthorized") {
          expire(SESSION_EXPIRED);
          return;
        }
        const scheduleAuto = ANSWER_ERROR_COPY[failure.kind].autoRetry && !autoRetried;
        const waitS = failure.retryAfterS ?? DEFAULT_RETRY_AFTER_S;
        update(id, {
          state: "failed",
          failure,
          autoRetryAt: scheduleAuto ? Date.now() + waitS * 1000 : null,
        });
        if (scheduleAuto) addTimer(id, () => void run(id, question, true), waitS * 1000);
      } finally {
        if (controllers.current.get(id) === controller) controllers.current.delete(id);
      }
    },
    [addTimer, apiKey, clearTimers, expire, update],
  );

  const ask = useCallback(
    (question: string) => {
      const id = `turn-${++sequence}`;
      setTurns((prev) => [
        ...prev,
        { id, question, askedAt: new Date(), state: "loading", slow: false, autoRetryAt: null, autoRetried: false },
      ]);
      void run(id, question, false);
    },
    [run],
  );

  const retry = useCallback(
    (id: string) => {
      const turn = turns.find((t) => t.id === id);
      if (turn) void run(id, turn.question, true);
    },
    [run, turns],
  );

  const cancelAutoRetry = useCallback(
    (id: string) => {
      clearTimers(id);
      update(id, { autoRetryAt: null, autoRetried: true });
    },
    [clearTimers, update],
  );

  useEffect(() => {
    const allTimers = timers.current;
    const allControllers = controllers.current;
    return () => {
      allTimers.forEach((list) => list.forEach(clearTimeout));
      allControllers.forEach((c) => c.abort());
    };
  }, []);

  const pending = turns.some((t) => t.state === "loading");
  return { turns, ask, retry, cancelAutoRetry, pending };
}

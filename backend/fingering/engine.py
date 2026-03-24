"""指法规则引擎

为音符序列分配钢琴指法。
核心：识别连续级进段落（≥2个同向小音程），分配连续手指。
"""

from typing import Optional

from backend.models.score import NoteData, Measure, DifficultyLevel


class FingeringEngine:
    """指法分配引擎。"""

    BLACK_KEY_CLASSES = {1, 3, 6, 8, 10}

    def __init__(self):
        pass

    def assign_to_measures(
        self, measures: list[Measure], difficulty: DifficultyLevel
    ) -> list[Measure]:
        all_notes = []
        for mi, measure in enumerate(measures):
            for ni, note in enumerate(measure.notes):
                if not note.is_rest:
                    all_notes.append((mi, ni, note))
        if not all_notes:
            return measures

        fingerings = self._assign([n[2] for n in all_notes])
        if difficulty == DifficultyLevel.HARD:
            fingerings = self._filter(fingerings, [n[2] for n in all_notes])

        for idx, (mi, ni, _) in enumerate(all_notes):
            if fingerings[idx] is not None:
                old = measures[mi].notes[ni]
                measures[mi].notes[ni] = NoteData(
                    pitch=old.pitch, duration=old.duration,
                    velocity=old.velocity, fingering=fingerings[idx],
                    is_rest=old.is_rest,
                )
        return measures

    def _is_black(self, p):
        return (p % 12) in self.BLACK_KEY_CLASSES

    def _assign(self, notes: list[NoteData]) -> list[Optional[int]]:
        n = len(notes)
        if n == 0:
            return []

        pitches = [x.pitch for x in notes]
        fingers = [0] * n

        # Step 1: 检测每个位置的级进方向
        # step_dir[i] = +1(上行级进), -1(下行级进), 0(跳进/同音)
        step_dir = [0] * n
        for i in range(1, n):
            d = pitches[i] - pitches[i-1]
            if 0 < d <= 3:
                step_dir[i] = 1
            elif -3 <= d < 0:
                step_dir[i] = -1

        # Step 2: 找到连续级进段落（≥2个同向级进音程）
        # 标记哪些位置属于级进段落
        in_run = [False] * n
        run_fingers = [0] * n  # 级进段落内的指法

        i = 1
        while i < n:
            if step_dir[i] == 0:
                i += 1
                continue
            # 找到一个级进段落
            d = step_dir[i]
            run_start = i - 1  # 段落从级进前一个音开始
            run_end = i
            while run_end + 1 < n and step_dir[run_end + 1] == d:
                run_end += 1
            # 段落长度 = run_end - run_start + 1
            # 至少需要2个音程（3个音）才算"段落"
            # 但即使2个音也分配连续手指
            if run_end - run_start >= 1:
                # 这是一个级进段落
                # 确定段落起始指法
                if not in_run[run_start]:
                    # 第一个音还没被分配
                    start_f = self._pick_start_finger(pitches, run_start, d, run_end)
                    run_fingers[run_start] = start_f
                    in_run[run_start] = True
                else:
                    start_f = run_fingers[run_start]

                # 给后续音分配连续手指
                f = start_f
                for j in range(run_start + 1, run_end + 1):
                    if d == 1:  # 上行
                        f = max(1, f - 1)
                    else:       # 下行
                        f = min(5, f + 1)
                    run_fingers[j] = f
                    in_run[j] = True

            i = run_end + 1

        # Step 3: 给非级进位置分配指法（跳进和孤立级进）
        early = pitches[:min(8, n)]
        center = (min(early) + max(early)) / 2
        if not in_run[0]:
            fingers[0] = self._center_finger(pitches[0], center)
        else:
            fingers[0] = run_fingers[0]

        for i in range(1, n):
            if in_run[i]:
                fingers[i] = run_fingers[i]
            else:
                # 跳进
                f = self._jump_finger(pitches, i, fingers[i-1], pitches[i-1])
                fingers[i] = f
                # 如果这个音是后续级进段落的起点，更新段落的起始指法
                if i + 1 < n and step_dir[i + 1] != 0:
                    d = step_dir[i + 1]
                    # 找这个级进段落的范围
                    run_end = i + 1
                    while run_end + 1 < n and step_dir[run_end + 1] == d:
                        run_end += 1
                    # 用当前指法作为段落起点，重新分配
                    run_fingers[i] = f
                    in_run[i] = True
                    cf = f
                    for j in range(i + 1, run_end + 1):
                        if d == 1:
                            cf = max(1, cf - 1)
                        else:
                            cf = min(5, cf + 1)
                        run_fingers[j] = cf
                        in_run[j] = True
                    fingers[i] = f

        # Step 4: 黑键修正
        for i in range(n):
            if self._is_black(pitches[i]) and fingers[i] in (1, 5):
                fingers[i] = 2 if fingers[i] == 1 else 4

        return fingers

    def _pick_start_finger(self, pitches, start_idx, direction, end_idx):
        """为级进段落选择起始手指。

        上行段落：从高指号开始（如5或4），往下递减
        下行段落：从低指号开始（如1或2），往上递增
        """
        run_len = end_idx - start_idx  # 音程个数
        if direction == 1:  # 上行
            # 需要 run_len+1 个连续手指（递减）
            start = min(5, run_len + 1)
            return max(1, start)
        else:  # 下行
            # 需要 run_len+1 个连续手指（递增）
            start = max(1, 5 - run_len)
            return start

    def _center_finger(self, pitch, center):
        off = pitch - center
        if off >= 3: return 1
        elif off >= 1: return 2
        elif off >= -1: return 3
        elif off >= -3: return 4
        else: return 5

    def _jump_finger(self, pitches, idx, prev_f, prev_p):
        """跳进后选择手指。

        简化策略：只用1或5作为大跳后的锚点
        - 跳到更高：用1指（低指）
        - 跳到更低：用5指（高指）

        这样可以避免出现311或511这种不合理的指法。
        后续级进会自然使用2-3-4。
        """
        target = pitches[idx]
        jump = target - prev_p
        if jump > 0:
            return 1  # 跳到更高，用低指
        else:
            return 5  # 跳到更低，用高指

    def _filter(self, fingerings, notes):
        if len(fingerings) <= 1:
            return fingerings
        filtered = [fingerings[0]]
        for i in range(1, len(notes)):
            if abs(notes[i].pitch - notes[i-1].pitch) > 2:
                filtered.append(fingerings[i])
            else:
                filtered.append(None)
        return filtered

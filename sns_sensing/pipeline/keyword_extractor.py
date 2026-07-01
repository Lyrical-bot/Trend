import math
from collections import defaultdict, Counter
from typing import List, Dict, Tuple

class KeywordExtractor:
    def __init__(self):
        self.doc_count = 0
        self.word_freq = Counter()
        self.doc_freq = Counter()
        self.co_occurrence = defaultdict(Counter)
        
    def add_document(self, keywords: List[str]):
        """하나의 영상(문서)에서 추출된 키워드 목록을 입력받아 통계를 누적합니다."""
        self.doc_count += 1
        unique_keywords = set(keywords)
        
        for kw in keywords:
            self.word_freq[kw] += 1
            
        for kw in unique_keywords:
            self.doc_freq[kw] += 1
            
            # Co-occurrence 업데이트
            for other_kw in unique_keywords:
                if kw != other_kw:
                    self.co_occurrence[kw][other_kw] += 1
                    
    def calculate_pmi(self, min_co_occurrence=3) -> Dict[Tuple[str, str], float]:
        """PMI(Pointwise Mutual Information)를 계산합니다."""
        pmi_scores = {}
        total_words = sum(self.word_freq.values())
        if total_words == 0:
            return pmi_scores
            
        for w1, neighbors in self.co_occurrence.items():
            for w2, count in neighbors.items():
                if w1 < w2: # 중복 계산 방지
                    if count >= min_co_occurrence:
                        p_w1 = self.word_freq[w1] / total_words
                        p_w2 = self.word_freq[w2] / total_words
                        p_w1_w2 = count / total_words
                        
                        if p_w1 > 0 and p_w2 > 0 and p_w1_w2 > 0:
                            pmi = math.log2(p_w1_w2 / (p_w1 * p_w2))
                            pmi_scores[(w1, w2)] = pmi
        return pmi_scores

    def get_top_candidates(self, top_n=120) -> List[str]:
        """TF-IDF(단순화된 형태)와 빈도를 결합하여 유망 후보(단일 단어 및 N-gram)를 선별합니다."""
        scores = {}
        for kw, freq in self.word_freq.items():
            if freq >= 3: # 최소 3번 이상 등장한 단어만
                tf = freq
                idf = math.log10(self.doc_count / (1 + self.doc_freq[kw])) if self.doc_count > 0 else 0
                scores[kw] = tf * idf
                
        # 점수 순 정렬 후 top_n 반환
        sorted_candidates = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [kw for kw, score in sorted_candidates[:top_n]]
        
    def get_co_occurrences(self, min_count=3) -> List[Tuple[str, str, int]]:
        """DB 저장을 위한 co-occurrence 리스트 반환"""
        results = []
        for w1, neighbors in self.co_occurrence.items():
            for w2, count in neighbors.items():
                if w1 < w2 and count >= min_count:
                    results.append((w1, w2, count))
        return results

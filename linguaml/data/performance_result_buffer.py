from typing import Optional
from pydantic import BaseModel

# Imports from this package
from linguaml.hp import HPConfig
from .priority_queue import PriorityQueue

class PerformanceResult(BaseModel):
    
    hp_config: HPConfig
    accuracy: float

class PerformanceResultBuffer:
    
    def __init__(
            self, 
            capacity: int,
            internal_capacity: Optional[int] = None
        ) -> None:
        """Initialize a performance result buffer.

        Parameters
        ----------
        capacity : int
            The capacity of the buffer.
        internal_capacity : Optional[int], optional
            The internal capacity of the buffer, by default None.
            If None, then the internal capacity is set to 2 times the capacity.
        """
        
        self._capacity = capacity
        
        if internal_capacity is None:
            internal_capacity = capacity * 2
        self._internal_capacity = internal_capacity
        
        # High performance results stored in a priority queue
        self._results = PriorityQueue(
            get_priority=lambda result: -result.accuracy
        )
    
    def push(self, result: PerformanceResult) -> None:
        """Push a new result to the buffer.
        
        Parameters
        ----------
        result : PerformanceResult
            The result to be pushed.
        """
        
        self._results.push(result)
        
        # If the queue is full (the internal capacity is reached), 
        # remove the low performance results
        if len(self._results) > self._internal_capacity:
            # Throw away the low performance results
            results_to_keep = self._results.peek_first_n_items(self._capacity)
            
            # Clear the queue
            self._results.clear()
            
            # Push the high performance results back to the queue
            self._results.extend(results_to_keep)
            
    def peek_first_n_high_performance_results(self, n: int) -> list[PerformanceResult]:
        """Peek the first n high performance results in the buffer.
        
        Parameters
        ----------
        n : int
            The number of results to be peeked.

        Returns
        -------
        list[PerformanceResult]
            The first n high performance results in the buffer.
            If n is greater than the capacity, then return the results in the buffer.
        """
        
        # If n is greater than the capacity,
        # then return the results in the buffer
        if n > self._capacity:
            n = self._capacity
            
        return self._results.peek_first_n_items(n)
        
    def to_list(self) -> list[PerformanceResult]:
        """Return the results in the buffer as a list.

        Returns
        -------
        list[PerformanceResult]
            The results in the buffer ordered by accuracy in descending order.
        """
        
        # Note that the number of results is limited by the capacity
        n_results = min(len(self._results), self._capacity)
        
        return list(self._results.peek_first_n_items(n_results))
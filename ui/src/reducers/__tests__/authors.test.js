import { Map, fromJS, Set } from 'immutable';

import reducer, { initialState } from '../authors';
import {
  AUTHOR_ERROR,
  AUTHOR_REQUEST,
  AUTHOR_SUCCESS,
  CLEAR_STATE,
  AUTHOR_PUBLICATION_SELECTION_SET,
  AUTHOR_PUBLICATION_SELECTION_CLEAR,
  AUTHOR_SET_ASSIGN_DRAWER_VISIBILITY,
} from '../../actions/actionTypes';

describe('authors reducer', () => {
  it('default', () => {
    const state = reducer(undefined, {});
    expect(state).toEqual(initialState);
  });

  it('CLEAR_STATE', () => {
    const currentState = fromJS({
      data: {
        metadata: {
          control_number: 123456,
        },
      },
    });
    const state = reducer(currentState, { type: CLEAR_STATE });
    expect(state).toEqual(initialState);
  });

  it('AUTHOR_REQUEST', () => {
    const state = reducer(Map(), { type: AUTHOR_REQUEST });
    const expected = Map({ loading: true });
    expect(state).toEqual(expected);
  });

  it('AUTHOR_SUCCESS', () => {
    const payload = {
      metadata: {
        name: [
          {
            value: 'Jessica Jones',
          },
        ],
        facet_author_name: 'Jessica.J.1',
      },
    };
    const state = reducer(Map(), { type: AUTHOR_SUCCESS, payload });
    const expected = fromJS({
      loading: false,
      data: payload,
      error: initialState.get('error'),
    });
    expect(state).toEqual(expected);
  });

  it('AUTHOR_ERROR', () => {
    const state = reducer(Map(), {
      type: AUTHOR_ERROR,
      payload: {
        error: { message: 'error' },
      },
    });
    const expected = fromJS({
      loading: false,
      error: { message: 'error' },
      data: initialState.get('data'),
    });
    expect(state).toEqual(expected);
  });

  it('AUTHOR_PUBLICATION_SELECTION_SET when selected', () => {
    const payload = {
      publicationIds: [2, 3],
      selected: true,
    };
    const currentState = Map({ publicationSelection: Set([1, 2]) });
    const state = reducer(currentState, {
      type: AUTHOR_PUBLICATION_SELECTION_SET,
      payload,
    });
    const expected = fromJS({
      publicationSelection: Set([1, 2, 3]),
    });
    expect(state).toEqual(expected);
  });

  it('AUTHOR_PUBLICATION_SELECTION_SET when deselected', () => {
    const payload = {
      publicationIds: [2, 3],
      selected: false,
    };
    const currentState = Map({ publicationSelection: Set([1, 2]) });
    const state = reducer(currentState, {
      type: AUTHOR_PUBLICATION_SELECTION_SET,
      payload,
    });
    const expected = fromJS({
      publicationSelection: Set([1]),
    });
    expect(state).toEqual(expected);
  });

  it('AUTHOR_PUBLICATION_SELECTION_CLEAR', () => {
    const currentState = Map({ publicationSelection: Set([1, 2]) });
    const state = reducer(currentState, {
      type: AUTHOR_PUBLICATION_SELECTION_CLEAR,
    });
    const expected = fromJS({
      publicationSelection: Set(),
    });
    expect(state).toEqual(expected);
  });

  it('AUTHOR_SET_ASSIGN_DRAWER_VISIBILITY', () => {
    const currentState = Map({ isAssignDrawerVisible: false });
    const state = reducer(currentState, {
      type: AUTHOR_SET_ASSIGN_DRAWER_VISIBILITY,
      payload: { visible: true },
    });
    const expected = fromJS({
      isAssignDrawerVisible: true,
    });
    expect(state).toEqual(expected);
  });
});

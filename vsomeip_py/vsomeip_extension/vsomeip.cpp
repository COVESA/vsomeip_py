/*
SPDX-FileCopyrightText: Copyright (c) 2023 Contributors to COVESA

See the NOTICE file(s) distributed with this work for additional
information regarding copyright ownership.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
SPDX-FileType: SOURCE
SPDX-License-Identifier: Apache-2.0
*/

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <signal.h>
#ifdef __unix__
  #include<unistd.h>
  #include <vsomeip/vsomeip.hpp>
  #include <vsomeip/constants.hpp>
#else
  #include<windows.h>
  #include <vsomeip\vsomeip.hpp>
  #include <vsomeip\constants.hpp>
#endif
#include <cstdlib>
#include <chrono>
#include <thread>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>
#include <thread>
#include <mutex>
#include <list>
#include <iostream>
#include <exception>
#include <typeinfo>
#include <stdexcept>
using namespace std;

typedef uint16_t client_t;
typedef uint16_t session_t;
#define PY_INVALID_ARGUMENTS    "invalid arguments!"

static std::mutex _mutex;
static std::mutex _payload_mutex;
#ifndef __unix__
  static vsomeip::byte_t _data[65536];  // size limit for payload, windows not handle vectors well...  Todo: bigger?
  static Py_ssize_t _data_size = 0;
#endif

static void testing(const std::string &_name) {
    std::cout << "TESTING: " << _name << std::endl;
}

static void print_message(const std::shared_ptr<vsomeip::message> &message_) {
  std::shared_ptr<vsomeip::payload> its_payload = message_->get_payload();

  std::stringstream ss;
  for (vsomeip::length_t i = 0; i < its_payload->get_length(); i++)
    ss<<std::setw(2)<<std::setfill('0')<<std::hex<<(int)*(its_payload->get_data() + i)<<" ";

  // make looking kinda like vsomeip logs
  std::cout<<"message -> client/session ["<<std::setw(4)
           <<std::setfill('0')<<std::hex<<message_->get_client()<<"/"
           <<std::setw(4)<<std::setfill('0')<<std::hex
           <<message_->get_session()<< "]: "<<ss.str()<<std::endl;
}

static PyObject *payload_pack(std::shared_ptr<vsomeip::payload> pl) {
  return PyByteArray_FromStringAndSize((const char *)pl->get_data(), pl->get_length());
}

static std::shared_ptr<vsomeip::payload> payload_unpack(PyObject *pObj) {
  const char *raw_data = PyByteArray_AsString(pObj);
  Py_ssize_t raw_size = PyByteArray_Size(pObj);
  std::shared_ptr<vsomeip::payload> payload = vsomeip::runtime::get()->create_payload();

// windows was corrupting memory as was being release (think) before having been consumed, locks in-place to protect
#ifdef __unix__
  std::vector<vsomeip::byte_t> payload_data(raw_size);
  for (int i = 0; i < raw_size; i++)   // copy
      payload_data[i] = (vsomeip::byte_t)raw_data[i];

  payload = vsomeip::runtime::get()->create_payload();
  payload->set_data(payload_data);
#else
  _data_size = raw_size;
  for (Py_ssize_t i = 0; i < _data_size; i++) // copy
      _data[i] = (vsomeip::byte_t)raw_data[i];

  payload->set_data(_data, (vsomeip_v3::length_t)_data_size);
#endif

  return payload;
}

struct vsomeip_Entity {
  std::string name;
  std::shared_ptr<vsomeip::application> app;
  std::shared_ptr<std::thread> app_thread;

  int service_id;
  int instance_id;
  bool is_registered;
  std::map<int, std::list<PyObject*>> callback;
  std::map<int, std::list<PyObject*>> discovery;

  void on_availability(vsomeip::service_t service_id_, vsomeip::instance_t instance_id_, bool is_available_) {
    PyGILState_STATE gstate;
    gstate = PyGILState_Ensure();

    PyObject *arguments = Py_BuildValue("iii", service_id_, instance_id_, 1 ? is_available_: 0);

    for (PyObject *callback_object : discovery[0]) {
      try {
        PyObject_CallObject(callback_object, arguments); // invoke callback method
      }
      catch (...) {
        PyErr_SetString(PyExc_RuntimeError, "Check callback function!!!");
      }
    }
    Py_DECREF(arguments);

    PyGILState_Release(gstate);
  }

  void on_state(vsomeip::state_type_e state_) {
    PyGILState_STATE gstate;
    gstate = PyGILState_Ensure();

    if (state_ == vsomeip::state_type_e::ST_REGISTERED)
      is_registered = true;
    else
      is_registered = false;

    /*
    if (is_registered) {
        app->offer_service(service_id, instance_id);
    }
    */

    PyGILState_Release(gstate);
  }

  void message_handler(const std::shared_ptr<vsomeip::message> &message) {
    PyGILState_STATE gstate;
    gstate = PyGILState_Ensure();

    std::shared_ptr<vsomeip::payload> its_payload = message->get_payload();
    int service_id = message->get_service();
    int instance_id = message->get_instance();
    int message_id = message->get_method();
    int type = static_cast<std::underlying_type<vsomeip::message_type_e>::type>(message->get_message_type());

    // if no callback (i.e. registered) then no point to do anything further
    if (callback.count(message_id) <= 0 || callback[message_id].empty()) {
      PyGILState_Release(gstate);
      return;
    }

    int request_id = message->get_client() + message->get_session();

    PyObject *bytes_object = payload_pack(its_payload);
    PyObject *arguments = Py_BuildValue("iiiiOi", type, service_id, instance_id, message_id, bytes_object, request_id);

    for (PyObject *callback_object : callback[message_id]) {
      try {
        PyObject *result = PyObject_CallObject(callback_object, arguments); // invoke callback method
        if (PyErr_Occurred())
            PyErr_Print(); // or handle the exception as needed

        if (result != Py_None) { // respond if have data to send, Todo: actually follow the message types for proper action
        //cout<<"######################### "<<"HERE"<<" #########################"<<std::endl;
          if (PyObject_TypeCheck(result, &PyByteArray_Type)) {
            std::lock_guard<std::mutex> its_lock(_payload_mutex);  // lock before messing with buffer

            std::shared_ptr<vsomeip::message> its_response = vsomeip::runtime::get()->create_response(message);
            std::shared_ptr<vsomeip::payload> payload = payload_unpack(result);
            its_response->set_payload(payload);

            app->send(its_response);  // response to the request
          }
        }
        Py_DECREF(result);
      }
      catch (...) {
        PyErr_SetString(PyExc_RuntimeError, "Check callback function!!!");
      }
    }

    Py_DECREF(bytes_object);
    Py_DECREF(arguments);

    PyGILState_Release(gstate);
  }
};

/* global mapping for multiple services/clients by unique name */
std::map<std::string, map<int, std::map<int, vsomeip_Entity>>> _entity_mapping;

static PyObject *vsomeip_create_app(PyObject *self, PyObject *args) {
  std::lock_guard<std::mutex> guard(_mutex);

  const char *str_pointer;
  std::string name;
  int result = 0;
  int service_id, instance_id;

  if (!PyArg_ParseTuple(args, "sii", &str_pointer, &service_id, &instance_id))
    PyErr_SetString(PyExc_TypeError, PY_INVALID_ARGUMENTS);
  name = std::string(str_pointer);

  vsomeip_Entity vsomeip_entity;  // memory allocation happening
  vsomeip_entity.is_registered = false;
  vsomeip_entity.service_id = service_id;
  vsomeip_entity.instance_id = instance_id;
  vsomeip_entity.name = name;

  _entity_mapping[name][service_id][instance_id] = vsomeip_entity;
// windows creates a tightly coupled library and thus cannot pass complex data types, see: patch file for changes needed to vsomeip!
#ifdef __unix__
  _entity_mapping[name][service_id][instance_id].app = vsomeip::runtime::get()->create_application(vsomeip_entity.name);
#else
  _entity_mapping[name][service_id][instance_id].app = vsomeip::runtime::get()->create_application_std(vsomeip_entity.name.c_str());
#endif
  auto app = _entity_mapping[name][service_id][instance_id].app;
  app->init();

  auto instance = _entity_mapping[name][service_id][instance_id];

  auto register_availability_binder = std::bind(std::mem_fn(&vsomeip_Entity::on_availability), instance, std::placeholders::_1, std::placeholders::_2, std::placeholders::_3);
  app->register_availability_handler(vsomeip::ANY_SERVICE, vsomeip::ANY_INSTANCE, register_availability_binder);

  auto register_state_binder = std::bind(std::mem_fn(&vsomeip_Entity::on_state), instance, std::placeholders::_1);
  app->register_state_handler(register_state_binder);

  std::this_thread::sleep_for(chrono::milliseconds(125));  // todo: checking when actually ready (i.e. 'is_available')

  return Py_BuildValue("i", result);
}

static PyObject *vsomeip_request_service(PyObject *self, PyObject *args) {
  std::lock_guard<std::mutex> guard(_mutex);

  int service_id, instance_id;
  int result = 0;
  int version_major = 0x00, version_minor = 0x00;
  std::string name;
  char* str_pointer;

  if (!PyArg_ParseTuple(args, "siiii", &str_pointer, &service_id, &instance_id, &version_major, &version_minor))
    PyErr_SetString(PyExc_TypeError, PY_INVALID_ARGUMENTS);
  name = std::string(str_pointer);

  auto app = _entity_mapping[name][service_id][instance_id].app;

  app->request_service(service_id, instance_id);

  return Py_BuildValue("i", result);
}

static PyObject *vsomeip_stop(PyObject *self, PyObject *args) {
  int service_id, instance_id;
  int result = 0;
  std::string name;
  char* str_pointer;

  if (!PyArg_ParseTuple(args, "sii", &str_pointer, &service_id, &instance_id))
    PyErr_SetString(PyExc_TypeError, PY_INVALID_ARGUMENTS);
  name = std::string(str_pointer);

  auto app = _entity_mapping[name][service_id][instance_id].app;
  auto my_thread = _entity_mapping[name][service_id][instance_id].app_thread;

  try {
     app->stop_offer_service(service_id, instance_id);
     app->clear_all_handler();  // unregister all registered handlers
     app->release_service(service_id, instance_id);

     std::this_thread::sleep_for(chrono::milliseconds(125));  //  feel good wait, get messages out!
     return Py_BuildValue("i", result);

     if(app->is_routing()) {
       app->set_routing_state(vsomeip::routing_state_e::RS_SHUTDOWN); // Note:  tracing code it does not do anything for SHUTDOWN!
    #ifdef __unix__
        kill(my_thread->native_handle(), SIGTERM);
    #else
        TerminateThread(my_thread->native_handle(), SIGTERM);
    #endif
/*
       // vsomeip does weird checks if on the same thread to not block the stopping of router
       app->stop();
       if (std::this_thread::get_id() != my_thread->get_id())  // else deadlock
         if (my_thread->joinable())
           my_thread->join();
         else
           my_thread->detach();
*/
     } else {
       app->stop();
     }
    //vsomeip::runtime::get()->remove_application(name);
  }
  catch (...) {
    PyErr_SetString(PyExc_RuntimeError, "Failed to stop...");
  }
  return Py_BuildValue("i", result);
}

static void start(std::string name_, int service_id_, int instance_id_) {
  auto app = _entity_mapping[name_][service_id_][instance_id_].app;
  if(app->is_routing()) {
       ;
  }
  app->start();
}

static PyObject *vsomeip_start(PyObject *self, PyObject *args) {
  std::lock_guard<std::mutex> guard(_mutex);

  int result = 0;
  std::string name;
  int service_id, instance_id;
  char* str_pointer;

  if (!PyArg_ParseTuple(args, "sii", &str_pointer, &service_id, &instance_id))
    PyErr_SetString(PyExc_TypeError, PY_INVALID_ARGUMENTS);
  name = std::string(str_pointer);
  auto app = _entity_mapping[name][service_id][instance_id].app;
  auto instance = _entity_mapping[name][service_id][instance_id];

  _entity_mapping[name][service_id][instance_id].app_thread = std::make_shared<std::thread>(std::bind(&start, name, service_id, instance_id));
  _entity_mapping[name][service_id][instance_id].app_thread->detach();

  std::this_thread::sleep_for(chrono::milliseconds(125));  // todo: know when application is actually started

  return Py_BuildValue("i", result);
}

static PyObject *vsomeip_discovery_services(PyObject *self, PyObject *args) {
  std::lock_guard<std::mutex> guard(_mutex);
  int service_id, instance_id;
  int result = 0;
  std::string name;
  PyObject *callback_object;
  char* str_pointer;

  if (!PyArg_ParseTuple(args, "siiO", &str_pointer, &service_id, &instance_id, &callback_object))
    PyErr_SetString(PyExc_TypeError, PY_INVALID_ARGUMENTS);
  name = std::string(str_pointer);

  // make sure last argument is a function
  if (!PyCallable_Check(callback_object)) {
    PyErr_SetString(PyExc_TypeError, "need a callable object!");
  }

  Py_XINCREF(callback_object); // add a reference to new callback
  _entity_mapping[name][service_id][instance_id].discovery[0].push_back(callback_object);

  return Py_BuildValue("i", result);
}

static PyObject *vsomeip_register_message(PyObject *self, PyObject *args) {
  std::lock_guard<std::mutex> guard(_mutex);
  int service_id, instance_id, message_id;
  int result = 0;
  std::string name;
  PyObject *callback_object;
  char* str_pointer;

  if (!PyArg_ParseTuple(args, "siiiO", &str_pointer, &service_id, &instance_id, &message_id, &callback_object))
    PyErr_SetString(PyExc_TypeError, PY_INVALID_ARGUMENTS);
  name = std::string(str_pointer);

  // make sure last argument is a function
  if (!PyCallable_Check(callback_object)) {
    PyErr_SetString(PyExc_TypeError, "need a callable object!");
  }

  Py_XINCREF(callback_object); // add a reference to new callback
  _entity_mapping[name][service_id][instance_id].callback[message_id].push_back(callback_object);

  auto app = _entity_mapping[name][service_id][instance_id].app;
  auto instance = _entity_mapping[name][service_id][instance_id];

  auto ptr_to_func = std::mem_fn(&vsomeip_Entity::message_handler);
  auto register_message_binder = std::bind(ptr_to_func, instance, std::placeholders::_1);  // MAGIC!!!!!!!!!!!!!!!!!!
  if(message_id == 0xFFFF)
    app->register_message_handler(vsomeip::ANY_SERVICE, vsomeip::ANY_INSTANCE, vsomeip::ANY_METHOD, register_message_binder);
  else
    app->register_message_handler(service_id, instance_id, message_id, register_message_binder);

  return Py_BuildValue("i", result);
}

// global map avaiability callback
std::map<std::string, std::map<int, std::map<int, PyObject *>>> _availability_callbacks;

static PyObject *vsomeip_register_availability(PyObject *self, PyObject *args){
  std::lock_guard<std::mutex> guard(_mutex);
  int service_id, instance_id;
  int result = 0;
  std::string name;
  PyObject *callback_object;
  char *str_pointer;

  // get args
  if (!PyArg_ParseTuple(args, "siiO", &str_pointer, &service_id, &instance_id, &callback_object)){
    PyErr_SetString(PyExc_TypeError, PY_INVALID_ARGUMENTS);
    return Py_BuildValue("i", result);
  }
  name = std::string(str_pointer);

  // make sure last argument is a function
  if (!PyCallable_Check(callback_object)){
    PyErr_SetString(PyExc_TypeError, "need a callable object!");
    return Py_BuildValue("i", result);
  }

  // restore callback map
  Py_INCREF(callback_object);
  _availability_callbacks[name][service_id][instance_id] = callback_object;

  auto app = _entity_mapping[name][service_id][instance_id].app;
  if (app){
    app->register_availability_handler(
        service_id,
        instance_id,
        [name, service_id, instance_id](vsomeip::service_t _service, vsomeip::instance_t _instance, bool _is_available){
      // get callback from global map
      PyObject *callback = _availability_callbacks[name][_service][_instance];

      if (callback && PyCallable_Check(callback)){
        PyObject *args = Py_BuildValue("(iii)", _service, _instance, _is_available);
        if (!args){
          PyErr_Print();
          return;
        }

        try{
          PyGILState_STATE gstate;
          gstate = PyGILState_Ensure();
          PyObject_CallObject(callback, args);
          PyGILState_Release(gstate);

          if (PyErr_Occurred())
            PyErr_Print(); // or handle the exception as needed
          return;
        }
        catch (...){
          PyErr_SetString(PyExc_RuntimeError, "Check callback function!!!");
          return;
        }
        Py_DECREF(args);
        return;
      }
    });
  }
  return Py_BuildValue("i", result);
}

static PyObject *vsomeip_offer_service(PyObject *self, PyObject *args) {
  std::lock_guard<std::mutex> guard(_mutex);

  int service_id, instance_id;
  int version_major = 0x00, version_minor = 0x00;
  int result = 0;
  std::string name;
  char* str_pointer;

  if (!PyArg_ParseTuple(args, "siiii", &str_pointer, &service_id, &instance_id, &version_major, &version_minor))
    PyErr_SetString(PyExc_TypeError, PY_INVALID_ARGUMENTS);
  name = std::string(str_pointer);

  auto app = _entity_mapping[name][service_id][instance_id].app;
  app->offer_service(service_id, instance_id, version_major, version_minor);

  return Py_BuildValue("i", result);
}

static PyObject *vsomeip_send_service(PyObject *self, PyObject *args) {
  std::lock_guard<std::mutex> guard(_mutex);

  int service_id, instance_id, method_id;
  PyObject *data;
  int type = 0;
  int result = 0;
  std::string name;
  char* str_pointer;

  if (!PyArg_ParseTuple(args, "siiiiO", &str_pointer, &service_id, &instance_id, &method_id, &type, &data))
    PyErr_SetString(PyExc_TypeError, PY_INVALID_ARGUMENTS);
  name = std::string(str_pointer);

  if (PyObject_TypeCheck(data, &PyByteArray_Type)) {
      bool is_tcp = false;
      if (type == -1)
        is_tcp = true;

      std::lock_guard<std::mutex> its_lock(_payload_mutex);

      std::shared_ptr<vsomeip::message> its_request = vsomeip::runtime::get()->create_request(is_tcp);
      its_request->set_service(service_id);
      its_request->set_instance(instance_id);
      its_request->set_method(method_id);
      its_request->set_payload(payload_unpack(data));

      auto app = _entity_mapping[name][service_id][instance_id].app;
      app->send(its_request);

      int request_id = its_request->get_client() + its_request->get_session();
      result = request_id; // making the pt
  }
  //Py_DECREF(data);

  return Py_BuildValue("i", result);
}

static PyObject *vsomeip_request_event_service(PyObject *self, PyObject *args) {
  std::lock_guard<std::mutex> guard(_mutex);

  int service_id, instance_id, event_id, group_id;
  int version_major = 0x00, version_minor = 0x00;
  int result = 0;
  std::string name;
  char* str_pointer;

  if (!PyArg_ParseTuple(args, "siiiiii", &str_pointer, &service_id, &instance_id, &event_id, &group_id, &version_major, &version_minor))
    PyErr_SetString(PyExc_TypeError, PY_INVALID_ARGUMENTS);
  name = std::string(str_pointer);

  std::set<vsomeip::eventgroup_t> its_groups;
  its_groups.insert(group_id);

  auto app = _entity_mapping[name][service_id][instance_id].app;

// windows creates a tightly coupled library and thus cannot pass complex data types, see: patch file for changes needed to vsomeip!
#ifdef __unix__
  app->request_event(service_id, instance_id, event_id, its_groups, vsomeip::event_type_e::ET_FIELD);
#else
  uint16_t _groups[] = {(uint16_t)group_id};
  app->request_event_std(service_id, instance_id, event_id, _groups, vsomeip::event_type_e::ET_FIELD);
#endif
  app->subscribe(service_id, instance_id, group_id, version_major);

  return Py_BuildValue("i", result);
}

static PyObject *vsomeip_unrequest_event_service(PyObject *self, PyObject *args) {
  std::lock_guard<std::mutex> guard(_mutex);

  int service_id, instance_id, event_id, group_id;
  int result = 0;
  std::string name;
  char* str_pointer;

  if (!PyArg_ParseTuple(args, "siiii", &str_pointer, &service_id, &instance_id, &event_id, &group_id))
    PyErr_SetString(PyExc_TypeError, PY_INVALID_ARGUMENTS);
  name = std::string(str_pointer);

  std::set<vsomeip::eventgroup_t> its_groups;
  its_groups.insert(group_id);

  auto app = _entity_mapping[name][service_id][instance_id].app;
  if (group_id != vsomeip::ANY_EVENT)
      app->unsubscribe(service_id, instance_id, group_id);
  else
      app->release_event(service_id, instance_id, event_id);

  return Py_BuildValue("i", result);
}

static PyObject *vsomeip_notify_clients(PyObject *self, PyObject *args) {
  std::lock_guard<std::mutex> guard(_mutex);

  int service_id, instance_id, event_id;
  PyObject *data;
  int result = 0;
  std::string name;
  char* str_pointer;

  if (!PyArg_ParseTuple(args, "siiiO", &str_pointer, &service_id, &instance_id, &event_id, &data))
    PyErr_SetString(PyExc_TypeError, PY_INVALID_ARGUMENTS);
  name = std::string(str_pointer);

  {
    std::lock_guard<std::mutex> its_lock(_payload_mutex);

    std::shared_ptr<vsomeip::payload> payload = payload_unpack(data);
    auto app = _entity_mapping[name][service_id][instance_id].app;
    app->notify(service_id, instance_id, event_id, payload, true);
  }
  //Py_DECREF(data);

  return Py_BuildValue("i", result);
}

static PyObject *vsomeip_offer_event_service(PyObject *self, PyObject *args) {
  std::lock_guard<std::mutex> guard(_mutex);

  int service_id, instance_id, event_id, group_id;
  int result = 0;
  std::string name;
  char* str_pointer;

  if (!PyArg_ParseTuple(args, "siiii",&str_pointer, &service_id, &instance_id, &event_id, &group_id))
    PyErr_SetString(PyExc_TypeError, PY_INVALID_ARGUMENTS);
  name = std::string(str_pointer);

  std::set<vsomeip::eventgroup_t> its_groups;
  its_groups.insert((uint16_t) group_id);

  auto app = _entity_mapping[name][service_id][instance_id].app;

// windows creates a tightly coupled library and thus cannot pass complex data types, see: patch file for changes needed to vsomeip!
#ifdef __unix__
  app->offer_event(service_id, instance_id, static_cast<vsomeip::event_t>(event_id), its_groups,  
                        vsomeip::event_type_e::ET_FIELD, std::chrono::milliseconds::zero(), // std::chrono::milliseconds(1000)
                        false, true, nullptr, vsomeip::reliability_type_e::RT_UNKNOWN);
#else
  uint16_t _groups[] = {(uint16_t)group_id};
  app->offer_event_std(service_id, instance_id, static_cast<vsomeip::event_t>(event_id), _groups,
                        vsomeip::event_type_e::ET_FIELD, std::chrono::milliseconds::zero(), // std::chrono::milliseconds(1000)
                        false, true, nullptr, vsomeip::reliability_type_e::RT_UNKNOWN);
#endif

  return Py_BuildValue("i", result);
}

static PyObject *vsomeip_testing(PyObject *self, PyObject *args) {
  int result = 0;
  vsomeip_create_app(self, args);

  return Py_BuildValue("i", result);
}

/**************************************************************************************************/
// *** Module Setup ***/
/**************************************************************************************************/

/* Table of module-level functions */
static PyMethodDef PyMethodDef_vsomeip[] = {
    {"create", vsomeip_create_app, METH_VARARGS, "create application"},
    {"start", vsomeip_start, METH_VARARGS, "start vsomeip application"},
    {"stop", vsomeip_stop, METH_VARARGS, "stop vsomeip application"},
    {"register_message", vsomeip_register_message, METH_VARARGS, "register message"},
    {"register_availability", vsomeip_register_availability, METH_VARARGS, "register availability callback"},
    {"offer_service", vsomeip_offer_service, METH_VARARGS, "offer service"},
    {"request_service", vsomeip_request_service, METH_VARARGS, "request service"},
    {"send_service", vsomeip_send_service, METH_VARARGS, "request message to service"},
    {"offer_event_service", vsomeip_offer_event_service, METH_VARARGS, "offering events"},
    {"request_event_service", vsomeip_request_event_service, METH_VARARGS, "requesting/subscribing event"},
    {"unrequest_event_service", vsomeip_unrequest_event_service, METH_VARARGS, "unrequesting/unsubscribing event"},
    {"notify_clients", vsomeip_notify_clients, METH_VARARGS, "fire event"},
    {"discovery_services", vsomeip_discovery_services, METH_VARARGS, "when services discovered"},
    {"testing", vsomeip_testing, METH_VARARGS, "testing..."},
    {NULL, NULL, 0, NULL} /* Sentinel */
};

/* Information needed to create a module */
static struct PyModuleDef PyModuleDef_vsomeip = {
    PyModuleDef_HEAD_INIT,
    "vsomeip_ext",
    NULL, // doc
    -1, // module keeps state in global variables
    PyMethodDef_vsomeip
};


/* Module entry-point */
PyMODINIT_FUNC PyInit_vsomeip_ext(void) {
  auto module = PyModule_Create(&PyModuleDef_vsomeip);
  return module;
}

/* Initialize python hooks */
int main(int argc, char *argv[]) {
  wchar_t *program = Py_DecodeLocale(argv[0], NULL);
  if (program == NULL) {
    std::cerr<<"Fatal Error!"<<std::endl;
    return -1;
  }

#if PY_VERSION_HEX < 0x030B0000  // 3.11.XX
  Py_SetProgramName(program);
  Py_Initialize();
#else
  PyStatus status;
  PyConfig config;
  PyConfig_InitPythonConfig(&config);

  /* Set the program name. Implicitly pre-initialize Python. */
  status = PyConfig_SetString(&config, &config.program_name, program);
  if (PyStatus_Exception(status)) {
    std::cerr<<"Program Name Error!"<<std::endl;
    return -1;
  }

  status = Py_InitializeFromConfig(&config);
  if (PyStatus_Exception(status)) {
      std::cerr<<"Configuration Error!"<<std::endl;
      return -1;
  }
  PyConfig_Clear(&config);
#endif
   // Todo: loop through mapping to exit ALL applications
   //Py_AtExit();
   PyMem_RawFree(program);
  return 0;
}
